"""Embedding backends. Every backend returns L2-normalised float32 vectors,
so a dot product between two vectors is their cosine similarity."""

from __future__ import annotations

import numpy as np

from .config import Settings


class Embedder:
    name: str = "base"

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


def _normalise(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class LocalEmbedder(Embedder):
    """sentence-transformers model, downloaded once and run on the CPU."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.name = f"local:{model_name}"
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype="float32")
        vectors = self._model.encode(texts, batch_size=32, show_progress_bar=False)
        return _normalise(vectors)


class OpenAIEmbedder(Embedder):
    def __init__(self, api_key: str, model: str):
        from openai import OpenAI

        self.name = f"openai:{model}"
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype="float32")
        vectors = []
        for start in range(0, len(texts), 100):
            response = self._client.embeddings.create(model=self._model, input=texts[start : start + 100])
            vectors.extend(item.embedding for item in response.data)
        return _normalise(np.array(vectors))


_cache: dict[str, Embedder] = {}


def get_embedder(settings: Settings) -> Embedder:
    """Build (or reuse) the embedder the settings ask for."""
    if settings.embedding_backend == "openai":
        key = f"openai:{settings.openai_embedding_model}"
        if key not in _cache:
            _cache[key] = OpenAIEmbedder(settings.openai_api_key, settings.openai_embedding_model)
        return _cache[key]
    key = f"local:{settings.local_embedding_model}"
    if key not in _cache:
        _cache[key] = LocalEmbedder(settings.local_embedding_model)
    return _cache[key]
