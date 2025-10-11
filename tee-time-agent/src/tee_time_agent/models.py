"""Shared data models used across the tee time agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TeeTimeSlot:
    """Structured representation of a single tee time."""

    time: str
    status: str
    available_slots: Optional[int]
    is_bookable: bool
    notes: Optional[str] = None


@dataclass
class TeeSheetAnalysis:
    """Result produced by the summarisation model."""

    date_iso: str
    day_name: str
    summary: str
    tee_times: list[TeeTimeSlot]
    warnings: list[str]
    source_url: str
    model_used: str
    model_raw_response: str
