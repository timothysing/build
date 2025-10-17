"""Summary builder for Edulink reports."""

from __future__ import annotations

from datetime import date
from typing import List

from .models import BehaviourEntry, EdulinkReport, HomeworkItem, MailEntry
from .utils import normalise_whitespace


def build_summary(report: EdulinkReport) -> str:
    """Return a human-friendly message summarising the report."""

    lines: List[str] = []
    heading_name = f" for {report.child_name}" if report.child_name else ""
    lines.append(f"Edulink daily summary{heading_name} — {report.generated_at.strftime('%A %d %B %Y')}")
    lines.append("")

    # Homework
    if report.homework_outstanding:
        lines.append("📚 Outstanding homework:")
        for item in report.homework_outstanding:
            subject = _fallback(item.subject, "Subject unknown")
            title = _fallback(item.title, "Untitled task")
            due = item.due_date.strftime("%d %b %Y") if item.due_date else "No due date"
            teacher = f" — {item.set_by}" if item.set_by else ""
            lines.append(f" • {subject}: {title}{teacher} (due {due})")
    else:
        lines.append("📚 No outstanding homework today.")
    lines.append("")

    # Behaviour
    if report.total_achievement_points is not None:
        lines.append(f"⭐ Achievement points: {report.total_achievement_points}")
    else:
        lines.append("⭐ Achievement points: unavailable")

    if report.behaviour_new:
        lines.append("   New entries from yesterday:")
        for entry in report.behaviour_new:
            cat = _fallback(entry.category, "General")
            pts = f"{entry.points:+d}" if entry.points is not None else "N/A"
            desc = _fallback(entry.description, "No description provided")
            staff = f" ({entry.staff})" if entry.staff else ""
            lines.append(f"   • {cat}: {desc}{staff} — {pts} points")
    else:
        lines.append("   No new behaviour entries yesterday.")
    lines.append("")

    # Mailbox
    if report.mailbox_new:
        lines.append("📬 New communicator messages (yesterday):")
        for mail in report.mailbox_new:
            sender = _fallback(mail.sender, "Unknown sender")
            subject = _fallback(mail.subject, "No subject")
            summary = _fallback(mail.summary, "")
            summary_suffix = f" – {summary}" if summary else ""
            lines.append(f" • {sender}: {subject}{summary_suffix}")
    else:
        lines.append("📬 No new communicator messages yesterday.")

    lines.append("")
    lines.append("Have a great day!")
    return "\n".join(lines)


def _fallback(value: str | None, default: str) -> str:
    candidate = normalise_whitespace(value or "")
    return candidate if candidate else default
