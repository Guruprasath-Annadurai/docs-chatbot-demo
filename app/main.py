"""FastAPI app. Run with:  uvicorn app.main:create_app --factory --port 8000"""

from __future__ import annotations

import logging
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator

from .config import Settings
from .embeddings import Embedder, get_embedder
from .ingest import SUPPORTED_EXTENSIONS, UnsupportedFileType
from .leads import EMAIL_RE, LeadStore
from .rag import ChatService, LLMUnavailable
from .ratelimit import RateLimiter

log = logging.getLogger("docs_chatbot")
STATIC = Path(__file__).parent / "static"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question is empty")
        return value.strip()


class LeadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200)
    question: str = Field(min_length=1, max_length=2000)
    page_url: str | None = Field(default=None, max_length=500)

    @field_validator("name", "question")
    @classmethod
    def strip(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("this field is empty")
        return value.strip()

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip()
        if not EMAIL_RE.match(value):
            raise ValueError("that doesn't look like an email address")
        return value


def create_app(settings: Settings | None = None, embedder: Embedder | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = settings or Settings.from_env()
    try:
        settings.validate()
    except ValueError as exc:
        log.error("Configuration problem: %s", exc)
        raise SystemExit(f"Configuration problem: {exc}") from exc

    if settings.effective_answer_mode == "extractive":
        log.info(
            "No LLM in use (ANSWER_MODE=%s, OPENAI_API_KEY %s). Answers will be the best-matching "
            "passages from your documents.",
            settings.answer_mode,
            "set" if settings.llm_available else "not set",
        )

    embedder = embedder or get_embedder(settings)
    service = ChatService(settings, embedder)
    leads = LeadStore(Path(settings.data_dir) / "leads.db")
    limiter = RateLimiter(settings.rate_limit_per_minute)

    if settings.load_sample_docs and len(service.store) == 0 and Path(settings.sample_docs_dir).is_dir():
        loaded = service.ingest_folder(Path(settings.sample_docs_dir))
        log.info("Loaded sample documents: %s", loaded)

    app = FastAPI(title="Docs chatbot demo", version="0.1.0")
    app.state.settings, app.state.service, app.state.leads = settings, service, leads
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Admin-Token"],
    )

    # ------------------------------------------------------- helpers

    def client_ip(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def rate_limited(request: Request) -> None:
        allowed, retry_after = limiter.allow(f"{client_ip(request)}:{request.url.path}")
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    def is_admin(request: Request) -> bool:
        token = request.headers.get("X-Admin-Token", "")
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
        return bool(settings.admin_token) and secrets.compare_digest(token.strip(), settings.admin_token)

    def require_admin(request: Request) -> None:
        if not settings.admin_token:
            raise HTTPException(503, "Admin endpoints are off. Set ADMIN_TOKEN in .env to turn them on.")
        if not is_admin(request):
            raise HTTPException(401, "Missing or wrong admin token.")

    def can_edit_documents(request: Request) -> None:
        if not settings.public_uploads:
            require_admin(request)

    # --------------------------------------------------------- pages

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/widget.js", include_in_schema=False)
    def widget() -> FileResponse:
        return FileResponse(STATIC / "widget.js", media_type="application/javascript")

    @app.get("/widget-demo", include_in_schema=False)
    def widget_demo() -> FileResponse:
        return FileResponse(STATIC / "widget-demo.html")

    # ----------------------------------------------------------- API

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "bot_name": settings.bot_name,
            "answer_mode": settings.effective_answer_mode,
            "llm_model": settings.llm_model if settings.effective_answer_mode == "llm" else None,
            "embeddings": embedder.name,
            "documents": len(service.store.sources()),
            "chunks": len(service.store),
            "public_uploads": settings.public_uploads,
        }

    @app.get("/api/documents")
    def list_documents() -> dict:
        return {"documents": [{"name": n, "chunks": c} for n, c in sorted(service.store.sources().items())]}

    @app.post("/api/documents", dependencies=[Depends(rate_limited), Depends(can_edit_documents)])
    async def upload(files: list[UploadFile] = File(...)) -> dict:
        limit = settings.max_upload_mb * 1024 * 1024
        results, errors = [], []
        for file in files:
            name = Path(file.filename or "").name
            if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
                errors.append({"name": name, "error": f"Unsupported type. Use {', '.join(sorted(SUPPORTED_EXTENSIONS))}."})
                continue
            data = await file.read(limit + 1)
            if len(data) > limit:
                errors.append({"name": name, "error": f"Larger than {settings.max_upload_mb} MB."})
                continue
            try:
                results.append({"name": name, "chunks": service.ingest(name, data)})
            except (UnsupportedFileType, ValueError) as exc:
                errors.append({"name": name, "error": str(exc)})
            except Exception as exc:  # a corrupt PDF, for example
                log.exception("Failed to index %s", name)
                errors.append({"name": name, "error": f"Couldn't read this file ({type(exc).__name__})."})
        if not results and errors:
            return JSONResponse(status_code=400, content={"indexed": [], "errors": errors})
        return {"indexed": results, "errors": errors}

    @app.delete("/api/documents/{name}", dependencies=[Depends(can_edit_documents)])
    def delete_document(name: str) -> dict:
        if not service.store.delete(Path(name).name):
            raise HTTPException(404, "No document with that name.")
        return {"deleted": name}

    @app.post("/api/chat", dependencies=[Depends(rate_limited)])
    def chat(body: ChatRequest) -> dict:
        try:
            return service.ask(body.question).to_dict()
        except LLMUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/api/leads", status_code=201, dependencies=[Depends(rate_limited)])
    def create_lead(body: LeadRequest) -> dict:
        lead_id = leads.add(body.name, body.email, body.question, body.page_url)
        return {"id": lead_id, "message": "Thanks! Someone will get back to you by email."}

    @app.get("/api/leads/export", dependencies=[Depends(require_admin)])
    def export_leads(format: str = "json"):
        if format == "csv":
            return PlainTextResponse(
                leads.to_csv(),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=leads.csv"},
            )
        return {"leads": leads.all()}

    return app
