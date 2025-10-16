"""Core datatypes for the Marcel Schneider news monitor."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class NewsItem:
    """A single news entry sourced from europeantour.com."""

    identifier: str
    title: str
    url: str
    published: datetime
    summary: Optional[str] = None

    def to_row(self) -> tuple[str, str, str, Optional[str], str]:
        """Return a tuple suitable for SQLite insertion."""
        return (
            self.identifier,
            self.title,
            self.url,
            self.summary,
            self.published.isoformat(timespec="seconds"),
        )
