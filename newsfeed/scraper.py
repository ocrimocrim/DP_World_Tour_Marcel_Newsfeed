"""Fetching and parsing news from europeantour.com."""
from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover - optional dependency at runtime
    curl_requests = None

from .types import NewsItem

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://www.europeantour.com"
PLAYER_NEWS_URL = (
    "https://www.europeantour.com/players/marcel-schneider-35703/news?tour=dpworld-tour"
)

_CURL_IMPERSONATIONS = [
    (
        "chrome120",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        {
            "sec-ch-ua": '"Chromium";v="120", "Not A(Brand";v="24", "Google Chrome";v="120"',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-mobile": "?0",
        },
    ),
    (
        "edge120",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        {
            "sec-ch-ua": '"Chromium";v="120", "Not A(Brand";v="24", "Microsoft Edge";v="120"',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-mobile": "?0",
        },
    ),
    (
        "safari17_0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        {
            "sec-ch-ua": '"Not A(Brand";v="99", "Chromium";v="118"',
            "sec-ch-ua-platform": '"macOS"',
            "sec-ch-ua-mobile": "?0",
        },
    ),
]

_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9,de;q=0.8",
    "de-DE,de;q=0.9,en;q=0.8",
]


class FetchError(RuntimeError):
    """Raised when the news feed cannot be retrieved."""


def _build_headers(
    user_agent: str | None = None, client_hints: dict[str, str] | None = None
) -> dict[str, str]:
    accept_language = random.choice(_ACCEPT_LANGUAGES)
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": accept_language,
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "upgrade-insecure-requests": "1",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "referer": BASE_URL + "/",
        "accept-encoding": "gzip, deflate, br",
    }
    if user_agent:
        headers["user-agent"] = user_agent
    if client_hints:
        headers.update(client_hints)
    return headers


def _build_scraper() -> cloudscraper.CloudScraper:
    # Cloudflare challenges appear sporadically; re-creating the scraper per
    # attempt helps cloudscraper negotiate a fresh challenge response.
    scraper = cloudscraper.create_scraper(
        delay=random.uniform(0.5, 1.5),
        browser={
            "browser": "chrome",
            "platform": "windows",
            "desktop": True,
            "mobile": False,
        },
    )
    scraper.headers.update(_build_headers(scraper.headers.get("User-Agent")))
    return scraper


def _fetch_with_curl_cffi(timeout: int, attempts: int) -> str:
    if curl_requests is None:  # pragma: no cover - optional dependency path
        raise FetchError("curl_cffi is not available")

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        impersonate, user_agent, client_hints = random.choice(_CURL_IMPERSONATIONS)
        headers = _build_headers(user_agent, client_hints)
        try:
            with curl_requests.Session() as session:
                session.impersonate = impersonate
                session.headers.update(headers)
                session.http2 = True
                session.timeout = timeout
                session.verify = True
                session.proxies = None
                warmup = session.get(
                    BASE_URL + "/",
                    allow_redirects=True,
                )
                if warmup.status_code >= 400:
                    LOGGER.debug(
                        "Warm-up request for %s returned %s",
                        BASE_URL,
                        warmup.status_code,
                    )
                time.sleep(random.uniform(0.6, 1.4))
                response = session.get(
                    PLAYER_NEWS_URL,
                    allow_redirects=True,
                )
            if response.status_code >= 400:
                last_error = FetchError(
                    f"Failed to retrieve news (status {response.status_code}) from {PLAYER_NEWS_URL}"
                )
                LOGGER.warning(
                    "curl_cffi attempt %s/%s blocked with status %s",
                    attempt,
                    attempts,
                    response.status_code,
                )
            else:
                return response.text
        except Exception as exc:  # noqa: BLE001 - log and retry
            LOGGER.warning(
                "curl_cffi attempt %s/%s to fetch news failed: %s",
                attempt,
                attempts,
                exc,
            )
            last_error = exc

        if attempt < attempts:
            time.sleep(random.uniform(2.0, 4.0))

    if last_error:
        raise FetchError(str(last_error)) from last_error
    raise FetchError(f"Failed to retrieve news from {PLAYER_NEWS_URL}")


def fetch_news_html(timeout: int = 30, attempts: int = 4) -> str:
    errors: list[Exception] = []

    if curl_requests is not None:
        try:
            return _fetch_with_curl_cffi(timeout=timeout, attempts=attempts)
        except Exception as exc:  # noqa: BLE001 - capture and fall back
            LOGGER.info("curl_cffi fetch failed, falling back to cloudscraper: %s", exc)
            errors.append(exc)

    last_error: Exception | None = None
    backoff = 1.75
    for attempt in range(1, attempts + 1):
        scraper = _build_scraper()
        try:
            warmup = scraper.get(BASE_URL + "/", timeout=timeout)
            if warmup.status_code >= 400:
                LOGGER.debug(
                    "Cloudscraper warm-up request for %s returned %s",
                    BASE_URL,
                    warmup.status_code,
                )
            time.sleep(random.uniform(0.5, 1.2))
            response = scraper.get(PLAYER_NEWS_URL, timeout=timeout)
            if response.status_code == 403:
                LOGGER.warning("Cloudscraper attempt %s/%s blocked by 403 status.", attempt, attempts)
                last_error = FetchError(
                    f"Failed to retrieve news (status {response.status_code}) from {PLAYER_NEWS_URL}"
                )
            elif response.status_code >= 400:
                last_error = FetchError(
                    f"Failed to retrieve news (status {response.status_code}) from {PLAYER_NEWS_URL}"
                )
            else:
                return response.text
        except Exception as exc:  # noqa: BLE001 - log and retry
            LOGGER.warning(
                "Cloudscraper attempt %s/%s to fetch news failed: %s",
                attempt,
                attempts,
                exc,
            )
            last_error = exc

        if attempt < attempts:
            sleep_for = backoff ** attempt
            time.sleep(sleep_for + random.uniform(0.0, 1.5))

    if last_error:
        for error in errors:
            LOGGER.debug("Earlier fetch attempt error: %s", error)
        raise FetchError(str(last_error)) from last_error
    raise FetchError(f"Failed to retrieve news from {PLAYER_NEWS_URL}")


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
