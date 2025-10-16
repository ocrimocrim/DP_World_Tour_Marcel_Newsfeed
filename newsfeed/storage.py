"""SQLite storage helpers for archiving fetched news."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Generator, Iterable, Optional

from .types import NewsItem


_SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    identifier TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    summary TEXT,
    published TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    raw_json TEXT
);
"""


class NewsArchive:
    """Lightweight wrapper around SQLite for persisting news items."""

    def __init__(self, path: str) -> None:
        db_path = Path(path)
        parent = db_path.parent
        if parent != Path("."):
            parent.mkdir(parents=True, exist_ok=True)
        self._path = str(db_path)
        self._ensure_schema()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._path)
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(_SCHEMA)
            conn.commit()

    def latest_identifier(self) -> Optional[str]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT identifier FROM news ORDER BY published DESC LIMIT 1"
            )
            row = cur.fetchone()
            return row[0] if row else None

    def has_item(self, identifier: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT 1 FROM news WHERE identifier = ? LIMIT 1", (identifier,)
            )
            return cur.fetchone() is not None

    def record_items(self, items: Iterable[NewsItem], raw_source: Optional[dict] = None) -> None:
        payload = json.dumps(raw_source, ensure_ascii=False) if raw_source else None
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn() as conn:
            for item in items:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO news (identifier, title, url, summary, published, retrieved_at, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*item.to_row(), now, payload),
                )
            conn.commit()

    def fetch_archive(self, limit: Optional[int] = None) -> list[NewsItem]:
        query = "SELECT identifier, title, url, summary, published FROM news ORDER BY published DESC"
        if limit is not None:
            query += " LIMIT ?"
            params: tuple[object, ...] = (limit,)
        else:
            params = ()

        with self._conn() as conn:
            cur = conn.execute(query, params)
            rows = cur.fetchall()

        items: list[NewsItem] = []
        for identifier, title, url, summary, published in rows:
            items.append(
                NewsItem(
                    identifier=identifier,
                    title=title,
                    url=url,
                    summary=summary,
                    published=datetime.fromisoformat(published),
                )
            )
        return items

    def export_ledger(self, path: str) -> None:
        """Write the full archive to a JSONL ledger for human inspection."""

        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT identifier, title, url, summary, published, retrieved_at
                FROM news
                ORDER BY published DESC
                """
            )
            rows = cur.fetchall()

        ledger_path = Path(path)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)

        with ledger_path.open("w", encoding="utf-8") as handle:
            for identifier, title, url, summary, published, retrieved_at in rows:
                handle.write(
                    json.dumps(
                        {
                            "identifier": identifier,
                            "title": title,
                            "url": url,
                            "summary": summary,
                            "published": published,
                            "retrieved_at": retrieved_at,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
