from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.embeddings import get_embedder
from app.main import create_app
from app.rag import ChatService

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DOCS = ROOT / "sample_docs"


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = dict(
        openai_api_key="",
        answer_mode="extractive",
        embedding_backend="local",
        data_dir=tmp_path / "data",
        sample_docs_dir=SAMPLE_DOCS,
        rate_limit_per_minute=1000,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(scope="session")
def embedder():
    # The real local model (downloaded once, ~90 MB), so tests check real retrieval.
    return get_embedder(Settings(embedding_backend="local"))


@pytest.fixture
def service(tmp_path, embedder):
    svc = ChatService(make_settings(tmp_path), embedder)
    svc.ingest_folder(SAMPLE_DOCS)
    return svc


@pytest.fixture
def make_client(tmp_path, embedder):
    def _make(**overrides) -> TestClient:
        return TestClient(create_app(make_settings(tmp_path, **overrides), embedder=embedder))

    return _make


@pytest.fixture
def client(make_client):
    return make_client()
