"""Project-relative configuration and source label normalization."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "incidents.sqlite3"
CONFIG_PATH = ROOT / "config" / "dashboard.json"
MISSING = {"", "--", "N/A", "NULL"}
METRIC_VERSION = "incident-counts-v1"


def database_path() -> Path:
    """Allow an explicit absolute or project-relative database path."""
    configured = os.environ.get("DFD_DB_PATH")
    path = Path(configured).expanduser() if configured else DEFAULT_DB
    return path if path.is_absolute() else ROOT / path


def settings() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def clean(value: object) -> str | None:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return None if value.upper() in MISSING else value


def location_key(value: object) -> str | None:
    value = clean(value)
    return re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip() if value else None


def unit_label(
    value: object, aliases: dict[str, str] | None = None
) -> tuple[str | None, bool]:
    value = clean(value)
    if not value:
        return None, False
    aliases = aliases if aliases is not None else settings()["unit_aliases"]
    key = re.sub(r"\s+", " ", value.upper()).strip()
    canonical = {name.upper(): name for name in aliases.values()}
    if key in aliases:
        return aliases[key], True
    if key in canonical:
        return canonical[key], True
    return value, False
