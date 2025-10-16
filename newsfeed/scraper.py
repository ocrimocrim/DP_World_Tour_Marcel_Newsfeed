"""Fetching and parsing news from europeantour.com."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup

from .types import NewsItem

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://www.europeantour.com"
PLAYER_NEWS_URL = (
    "https://www.europeantour.com/players/marcel-schneider-35703/news?tour=dpworld-tour"
)


class FetchError(RuntimeError):
    """Raised when the news feed cannot be retrieved."""


def _build_scraper() -> cloudscraper.CloudScraper:
    return cloudscraper.create_scraper(
        browser={
            "browser": "chrome",
            "platform": "windows",
            "mobile": False,
        }
    )


def fetch_news_html(timeout: int = 30) -> str:
    scraper = _build_scraper()
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": scraper.headers["User-Agent"],
    }
    response = scraper.get(PLAYER_NEWS_URL, headers=headers, timeout=timeout)
    if response.status_code >= 400:
        raise FetchError(
            f"Failed to retrieve news (status {response.status_code}) from {PLAYER_NEWS_URL}"
        )
    return response.text


def _extract_first(obj: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in obj and obj[key]:
            return obj[key]
    return None


def _normalise_url(url: str) -> str:
    return url if url.startswith("http") else urljoin(BASE_URL, url)


def _parse_datetime(value: str) -> datetime:
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    # Last resort: let fromisoformat handle relaxed cases
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Unable to parse datetime value: {value}") from exc


def _candidate_news_dict(obj: dict[str, Any]) -> bool:
    lowered = {key.lower() for key in obj}
    has_title = {"title", "headline", "name"} & lowered
    has_url = {"url", "slug", "permalink", "path"} & lowered
    has_date = {"date", "published", "publishdate", "publishdatetime"} & lowered
    return bool(has_title and has_url and has_date)


def _build_identifier(obj: dict[str, Any]) -> str:
    candidate = _extract_first(
        obj,
        "id",
        "identifier",
        "slug",
        "urlSlug",
        "canonicalSlug",
    )
    if candidate:
        return str(candidate)
    # Fallback: title + date hash
    title = str(_extract_first(obj, "title", "headline", "name") or "")
    published = str(
        _extract_first(obj, "publishDateTime", "publishDate", "published", "date")
        or ""
    )
    return f"{title.strip()}::{published.strip()}"


def parse_news(html: str) -> tuple[list[NewsItem], dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        raise FetchError("Could not locate Next.js data payload (__NEXT_DATA__).")

    payload = json.loads(script.string)
    items: list[NewsItem] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for entry in node:
                walk(entry)
        elif isinstance(node, dict):
            if _candidate_news_dict(node):
                try:
                    title = _extract_first(node, "title", "headline", "name")
                    url_raw = _extract_first(node, "url", "permalink", "path", "slug")
                    date_raw = _extract_first(
                        node,
                        "publishDateTime",
                        "publishDate",
                        "published",
                        "date",
                    )
                    summary = _extract_first(node, "summary", "description", "standfirst")
                    if not (title and url_raw and date_raw):
                        return
                    published = _parse_datetime(str(date_raw))
                    identifier = _build_identifier(node)
                    url = _normalise_url(str(url_raw))
                    items.append(
                        NewsItem(
                            identifier=identifier,
                            title=str(title).strip(),
                            url=url,
                            summary=(str(summary).strip() if summary else None),
                            published=published,
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - log and continue
                    LOGGER.debug("Failed to parse news item %s", node, exc_info=exc)
            for value in node.values():
                walk(value)

    walk(payload)
    unique: dict[str, NewsItem] = {}
    for item in items:
        if item.identifier not in unique or item.published > unique[item.identifier].published:
            unique[item.identifier] = item
    sorted_items = sorted(unique.values(), key=lambda item: item.published, reverse=True)
    if not sorted_items:
        LOGGER.warning("No news entries were parsed from the payload.")
    return sorted_items, payload


def fetch_news(timeout: int = 30) -> tuple[list[NewsItem], dict[str, Any]]:
    html = fetch_news_html(timeout=timeout)
    return parse_news(html)
