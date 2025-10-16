"""High-level orchestration for the news monitor."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from .discord import send_news
from .scraper import FetchError, fetch_news
from .storage import NewsArchive

LOGGER = logging.getLogger(__name__)


class MonitorService:
    def __init__(
        self,
        webhook_url: str,
        database_path: str,
        poll_interval: int = 3600,
        dry_run: bool = False,
        ledger_path: Optional[str] = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._archive = NewsArchive(database_path)
        self._poll_interval = poll_interval
        self._dry_run = dry_run
        self._ledger_path = ledger_path
        if self._ledger_path:
            Path(self._ledger_path).parent.mkdir(parents=True, exist_ok=True)

    def run_once(self) -> int:
        try:
            items, payload = fetch_news()
        except FetchError as exc:
            LOGGER.error("Fetching news failed: %s", exc)
            raise

        new_items = [item for item in items if not self._archive.has_item(item.identifier)]
        if new_items:
            LOGGER.info("Identified %s new news item(s).", len(new_items))
        else:
            LOGGER.info("No new news items detected.")

        self._archive.record_items(new_items or items, payload)

        if self._ledger_path:
            self._archive.export_ledger(self._ledger_path)

        if new_items and not self._dry_run:
            send_news(self._webhook_url, new_items)
        elif new_items:
            LOGGER.info("Dry run enabled - skipping Discord notification.")
        return len(new_items)

    def run_forever(self) -> None:
        LOGGER.info("Starting monitor loop with interval=%s seconds", self._poll_interval)
        while True:
            try:
                self.run_once()
            except Exception as exc:  # noqa: BLE001 - log and continue loop
                LOGGER.exception("Unexpected error during monitoring loop: %s", exc)
            time.sleep(self._poll_interval)

    def dump_archive(self, limit: Optional[int] = None) -> list[str]:
        return [f"{item.published.isoformat()} | {item.title} -> {item.url}" for item in self._archive.fetch_archive(limit)]
