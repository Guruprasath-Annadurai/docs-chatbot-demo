"""'Talk to a human' requests, stored in a local SQLite file."""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LeadStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    question TEXT NOT NULL,
                    page_url TEXT
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def add(self, name: str, email: str, question: str, page_url: str | None = None) -> int:
        created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO leads (created_at, name, email, question, page_url) VALUES (?, ?, ?, ?, ?)",
                (created, name, email, question, page_url),
            )
            return int(cursor.lastrowid)

    def all(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM leads ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def to_csv(self) -> str:
        buffer = io.StringIO()
        fields = ["id", "created_at", "name", "email", "question", "page_url"]
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        for row in self.all():
            writer.writerow(row)
        return buffer.getvalue()
