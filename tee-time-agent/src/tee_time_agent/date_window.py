"""Utilities for selecting the tee sheet target date."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List

WEEKDAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

WEEKEND_INDICES = {4, 5, 6}


@dataclass(frozen=True)
class TargetDate:
    """Represents a calendar date the agent should inspect."""

    value: date

    @property
    def iso(self) -> str:
        return self.value.isoformat()

    @property
    def verbose(self) -> str:
        return self.value.strftime("%A %d %B %Y")

    @property
    def day_name(self) -> str:
        return WEEKDAY_NAMES[self.value.weekday()]

    @property
    def is_weekend(self) -> bool:
        return self.value.weekday() in WEEKEND_INDICES


def compute_target_dates(today: date | None = None, *, lookahead_days: int = 10) -> List[TargetDate]:
    """
    Determine which date(s) to scrape based on the 10-day booking window.

    The agent mirrors the existing automation: it looks exactly ``lookahead_days`` ahead
    and only proceeds if that date falls on a Friday, Saturday, or Sunday.
    """
    today = today or date.today()
    target_value = today + timedelta(days=lookahead_days)
    target = TargetDate(target_value)
    return [target] if target.is_weekend else []
