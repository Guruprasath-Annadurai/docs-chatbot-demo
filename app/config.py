"""Settings, read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class Settings:
    # LLM
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    # "auto" uses the LLM when a key is set and extractive mode otherwise.
    # "llm" requires a key. "extractive" never calls an LLM.
    answer_mode: str = "auto"

    # Embeddings: "local" (sentence-transformers, runs on your machine) or "openai"
    embedding_backend: str = "local"
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_embedding_model: str = "text-embedding-3-small"

    # Retrieval
    chunk_size: int = 500
    chunk_overlap: int = 80
    top_k: int = 4
    similarity_threshold: float = 0.40

    # Storage
    data_dir: Path = Path("data")
    sample_docs_dir: Path = Path("sample_docs")
    load_sample_docs: bool = True

    # Guardrails and admin
    rate_limit_per_minute: int = 20
    admin_token: str = ""
    public_uploads: bool = True
    max_upload_mb: int = 10
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])

    # Branding for the UI and widget
    bot_name: str = "Little Crumb Assistant"

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            openai_api_key=env.get("OPENAI_API_KEY", "").strip(),
            llm_model=env.get("LLM_MODEL", cls.llm_model),
            answer_mode=env.get("ANSWER_MODE", cls.answer_mode).strip().lower(),
            embedding_backend=env.get("EMBEDDING_BACKEND", cls.embedding_backend).strip().lower(),
            local_embedding_model=env.get("LOCAL_EMBEDDING_MODEL", cls.local_embedding_model),
            openai_embedding_model=env.get("OPENAI_EMBEDDING_MODEL", cls.openai_embedding_model),
            chunk_size=int(env.get("CHUNK_SIZE", cls.chunk_size)),
            chunk_overlap=int(env.get("CHUNK_OVERLAP", cls.chunk_overlap)),
            top_k=int(env.get("TOP_K", cls.top_k)),
            similarity_threshold=float(env.get("SIMILARITY_THRESHOLD", cls.similarity_threshold)),
            data_dir=Path(env.get("DATA_DIR", "data")),
            sample_docs_dir=Path(env.get("SAMPLE_DOCS_DIR", "sample_docs")),
            load_sample_docs=_bool(env.get("LOAD_SAMPLE_DOCS"), True),
            rate_limit_per_minute=int(env.get("RATE_LIMIT_PER_MINUTE", cls.rate_limit_per_minute)),
            admin_token=env.get("ADMIN_TOKEN", "").strip(),
            public_uploads=_bool(env.get("PUBLIC_UPLOADS"), True),
            max_upload_mb=int(env.get("MAX_UPLOAD_MB", cls.max_upload_mb)),
            allowed_origins=_list(env.get("ALLOWED_ORIGINS"), ["*"]),
            bot_name=env.get("BOT_NAME", cls.bot_name),
        )

    def validate(self) -> None:
        """Raise ValueError with a plain explanation if the settings can't work."""
        if self.answer_mode not in {"auto", "llm", "extractive"}:
            raise ValueError("ANSWER_MODE must be one of: auto, llm, extractive.")
        if self.embedding_backend not in {"local", "openai"}:
            raise ValueError("EMBEDDING_BACKEND must be 'local' or 'openai'.")
        if self.embedding_backend == "openai" and not self.openai_api_key:
            raise ValueError(
                "EMBEDDING_BACKEND=openai needs OPENAI_API_KEY. Set the key in .env, "
                "or use EMBEDDING_BACKEND=local to embed documents on this machine."
            )
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE.")

    @property
    def llm_available(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def effective_answer_mode(self) -> str:
        if self.answer_mode == "auto":
            return "llm" if self.llm_available else "extractive"
        return self.answer_mode
