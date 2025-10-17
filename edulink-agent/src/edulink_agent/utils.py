"""Utility helpers for scraping and parsing."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from dateutil import parser as date_parser
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def get_zone(timezone_name: str) -> ZoneInfo:
    """Return a ZoneInfo instance, defaulting to UTC on failure."""
    try:
        return ZoneInfo(timezone_name)
    except Exception:  # pragma: no cover - fallback
        logger.warning("Unknown timezone %s, falling back to UTC", timezone_name)
        return ZoneInfo("UTC")


def now_in_timezone(timezone_name: str) -> datetime:
    """Current datetime in the configured timezone."""
    zone = get_zone(timezone_name)
    return datetime.now(tz=zone)


def yesterday(timezone_name: str) -> date:
    """Date for 'yesterday' in the configured timezone."""
    return (now_in_timezone(timezone_name) - timedelta(days=1)).date()


def parse_date(text: str) -> Optional[date]:
    """Best-effort parsing of a human-readable date string."""
    if not text:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None

    try:
        dt = date_parser.parse(cleaned, dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError) as exc:
        logger.debug("Failed to parse date '%s': %s", cleaned, exc)
        return None
    return dt.date()


def normalise_whitespace(text: str) -> str:
    """Collapse repeated whitespace into single spaces."""
    return re.sub(r"\s+", " ", text or "").strip()


def first_non_empty(values: Iterable[str | None]) -> Optional[str]:
    """Return the first non-empty string from an iterable."""
    for value in values:
        if value:
            stripped = value.strip()
            if stripped:
                return stripped
    return None
