"""Command line entrypoint for the Marcel Schneider news monitor."""
from __future__ import annotations

import argparse
import logging
import os
import sys

from .config import load_env
from .service import MonitorService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--webhook-url",
        help="Discord webhook URL that should receive new updates."
        " Can be set via NEWSFEED_WEBHOOK_URL.",
    )
    parser.add_argument(
        "--database",
        default="news_archive.sqlite3",
        help="Path to the SQLite database used to track sent news.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Polling interval in seconds (default: 3600).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and archive news without posting to Discord.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll instead of looping forever.",
    )
    parser.add_argument(
        "--dump-archive",
        action="store_true",
        help="Print the current archive to stdout instead of polling.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit when dumping the archive.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (default: INFO).",
    )
    parser.add_argument(
        "--ledger",
        default="archive/news_archive.jsonl",
        help="Path to a JSONL ledger that mirrors the SQLite archive."
        " Set to an empty string to skip writing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    load_env()

    webhook_url = args.webhook_url or os.getenv("NEWSFEED_WEBHOOK_URL")
    if not webhook_url and not (args.dump_archive or args.dry_run):
        parser.error("--webhook-url is required (or set NEWSFEED_WEBHOOK_URL).")

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    service = MonitorService(
        webhook_url=webhook_url or "",
        database_path=args.database,
        poll_interval=args.interval,
        dry_run=args.dry_run,
        ledger_path=args.ledger or None,
    )

    if args.dump_archive:
        for line in service.dump_archive(limit=args.limit):
            print(line)
        return 0

    if args.once:
        service.run_once()
        return 0

    service.run_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
