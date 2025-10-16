"""Discord webhook integration."""
from __future__ import annotations

import logging
from typing import Iterable

import requests

from .types import NewsItem

LOGGER = logging.getLogger(__name__)

MAX_EMBEDS_PER_REQUEST = 10
MAX_DESCRIPTION_LENGTH = 2048


def _chunked(items: list[NewsItem], size: int) -> Iterable[list[NewsItem]]:
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def _build_embed(item: NewsItem) -> dict:
    description = item.summary or ""
    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[: MAX_DESCRIPTION_LENGTH - 1] + "…"
    return {
        "title": item.title,
        "url": item.url,
        "description": description,
        "timestamp": item.published.replace(microsecond=0).isoformat() + "Z",
        "footer": {"text": "DP World Tour"},
    }


def send_news(webhook_url: str, items: list[NewsItem]) -> None:
    if not items:
        LOGGER.info("No new items to send to Discord.")
        return

    session = requests.Session()
    session.headers.update({"User-Agent": "MarcelNewsBot/1.0"})

    for batch in _chunked(items, MAX_EMBEDS_PER_REQUEST):
        payload = {
            "username": "Marcel Schneider News",
            "embeds": [_build_embed(item) for item in batch],
        }
        response = session.post(webhook_url, json=payload, timeout=15)
        if response.status_code >= 400:
            LOGGER.error(
                "Failed to send news to Discord: status %s, body=%s",
                response.status_code,
                response.text,
            )
            response.raise_for_status()
        LOGGER.info("Posted %s news item(s) to Discord.", len(batch))
