"""A small vector store on top of FAISS, saved to the data folder.

Vectors are kept in a numpy file next to the FAISS index, which makes
deleting a document easy: drop its rows and rebuild the index. That is
fine for the few thousand chunks a small business has.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np

from .ingest import Chunk


@dataclass
class SearchHit:
    score: float
    chunk: Chunk


class VectorStore:
    def __init__(self, directory: Path, embedder_name: str):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.embedder_name = embedder_name
        self._lock = threading.Lock()
        self._chunks: list[Chunk] = []
        self._vectors: np.ndarray | None = None
        self._index: faiss.Index | None = None
        self._load()

    # ------------------------------------------------------------ files

    @property
    def _meta_path(self) -> Path:
        return self.directory / "chunks.json"

    @property
    def _vectors_path(self) -> Path:
        return self.directory / "vectors.npy"

    @property
    def _index_path(self) -> Path:
        return self.directory / "index.faiss"

    def _load(self) -> None:
        if not (self._meta_path.exists() and self._vectors_path.exists()):
            return
        meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
        if meta.get("embedder") != self.embedder_name:
            # Vectors from a different model can't be compared with new queries.
            # Start empty; documents get re-indexed on the next upload or restart.
            return
        self._chunks = [Chunk(**item) for item in meta["chunks"]]
        self._vectors = np.load(self._vectors_path)
        if self._index_path.exists():
            self._index = faiss.read_index(str(self._index_path))
        else:
            self._rebuild_index()

    def _save(self) -> None:
        meta = {"embedder": self.embedder_name, "chunks": [c.to_dict() for c in self._chunks]}
        self._meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        if self._vectors is not None:
            np.save(self._vectors_path, self._vectors)
        if self._index is not None:
            faiss.write_index(self._index, str(self._index_path))

    def _rebuild_index(self) -> None:
        if self._vectors is None or len(self._vectors) == 0:
            self._index = None
            return
        index = faiss.IndexFlatIP(self._vectors.shape[1])  # inner product == cosine on normalised vectors
        index.add(self._vectors)
        self._index = index

    # ----------------------------------------------------------- public

    def __len__(self) -> int:
        return len(self._chunks)

    def sources(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for chunk in self._chunks:
            counts[chunk.source] = counts.get(chunk.source, 0) + 1
        return counts

    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        if not chunks:
            return
        with self._lock:
            self._remove(chunks[0].source)  # re-uploading a file replaces it
            self._chunks.extend(chunks)
            vectors = np.asarray(vectors, dtype="float32")
            self._vectors = vectors if self._vectors is None or len(self._vectors) == 0 else np.vstack([self._vectors, vectors])
            self._rebuild_index()
            self._save()

    def delete(self, source: str) -> bool:
        with self._lock:
            removed = self._remove(source)
            if removed:
                self._rebuild_index()
                self._save()
            return removed

    def _remove(self, source: str) -> bool:
        keep = [i for i, c in enumerate(self._chunks) if c.source != source]
        if len(keep) == len(self._chunks):
            return False
        self._chunks = [self._chunks[i] for i in keep]
        self._vectors = self._vectors[keep] if self._vectors is not None else None
        return True

    def clear(self) -> None:
        with self._lock:
            self._chunks, self._vectors, self._index = [], None, None
            for path in (self._meta_path, self._vectors_path, self._index_path):
                path.unlink(missing_ok=True)

    def search(self, query_vector: np.ndarray, k: int) -> list[SearchHit]:
        if self._index is None or not self._chunks:
            return []
        query = np.asarray(query_vector, dtype="float32").reshape(1, -1)
        scores, ids = self._index.search(query, min(k, len(self._chunks)))
        return [
            SearchHit(score=float(score), chunk=self._chunks[idx])
            for score, idx in zip(scores[0], ids[0])
            if idx != -1
        ]
