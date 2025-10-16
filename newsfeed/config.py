"""Lightweight helpers for configuration loading."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def load_env(paths: Iterable[str] | None = None) -> None:
    """Populate os.environ with values from .env-style files if present."""

    if paths is None:
        paths = (".env",)

    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            continue

        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
