"""Pydantic models representing scraped Edulink data."""

from __future__ import annotations

from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, Field


class HomeworkItem(BaseModel):
    """Outstanding homework entry."""

    subject: Optional[str] = None
    title: Optional[str] = None
    set_by: Optional[str] = Field(default=None, alias="teacher")
    due_date: Optional[date] = None
    submission_status: Optional[str] = None
    details: Optional[str] = None


class BehaviourEntry(BaseModel):
    """Behaviour record (achievement/points)."""

    date: Optional[date] = None
    category: Optional[str] = None
    points: Optional[int] = None
    description: Optional[str] = None
    staff: Optional[str] = None


class MailEntry(BaseModel):
    """Communicator mailbox item."""

    date: Optional[date] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    summary: Optional[str] = None


class EdulinkReport(BaseModel):
    """Complete Edulink summary."""

    generated_at: datetime
    timezone: str
    child_name: Optional[str] = None
    total_achievement_points: Optional[int] = None
    homework_outstanding: List[HomeworkItem] = Field(default_factory=list)
    behaviour_new: List[BehaviourEntry] = Field(default_factory=list)
    mailbox_new: List[MailEntry] = Field(default_factory=list)
    summary_text: str

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            date: lambda d: d.isoformat(),
        }
