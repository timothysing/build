"""Simple conversational layer for Edulink reports."""

from __future__ import annotations

from typing import List

from .models import EdulinkReport, HomeworkItem, BehaviourEntry, MailEntry


def answer_question(report: EdulinkReport, question: str) -> str:
    """Return a conversational response based on the question."""

    if not question:
        return "I didn't catch a question. Ask me about homework, behaviour, achievement points, or recent messages."

    text = question.lower()

    if "homework" in text or "assignment" in text or "tasks" in text:
        return _describe_homework(report.homework_outstanding)

    if "behaviour" in text or "behavior" in text or "achievement" in text or "points" in text:
        return _describe_behaviour(report.total_achievement_points, report.behaviour_new)

    if "mail" in text or "email" in text or "message" in text or "communicator" in text or "inbox" in text:
        return _describe_mail(report.mailbox_new)

    if "summary" in text or "everything" in text:
        return report.summary_text

    return (
        "I'm not sure how to help with that. "
        "Try asking about homework, behaviour/achievement points, or communicator messages."
    )


def _describe_homework(items: List[HomeworkItem]) -> str:
    if not items:
        return "There is no outstanding homework at the moment."
    lines = ["Here's the outstanding homework:"]
    for item in items:
        subject = item.subject or "Subject unknown"
        title = item.title or "Untitled task"
        due = item.due_date.strftime("%d %b %Y") if item.due_date else "no due date"
        teacher = f" set by {item.set_by}" if item.set_by else ""
        lines.append(f" • {subject}: {title}{teacher}, due {due}.")
    return "\n".join(lines)


def _describe_behaviour(total_points: int | None, entries: List[BehaviourEntry]) -> str:
    if total_points is None and not entries:
        return "I couldn't retrieve behaviour information right now."

    lines: List[str] = []
    if total_points is not None:
        lines.append(f"Total achievement points: {total_points}.")

    if entries:
        lines.append("Yesterday's behaviour entries:")
        for entry in entries:
            cat = entry.category or "General"
            desc = entry.description or "No description"
            staff = f" ({entry.staff})" if entry.staff else ""
            pts = f"{entry.points:+d}" if entry.points is not None else "N/A"
            lines.append(f" • {cat}{staff}: {desc} — {pts} points")
    else:
        lines.append("No new behaviour entries yesterday.")
    return "\n".join(lines)


def _describe_mail(entries: List[MailEntry]) -> str:
    if not entries:
        return "There were no new communicator messages yesterday."
    lines = ["Yesterday's communicator messages:"]
    for mail in entries:
        sender = mail.sender or "Unknown sender"
        subject = mail.subject or "No subject"
        summary = f" — {mail.summary}" if mail.summary else ""
        lines.append(f" • {sender}: {subject}{summary}")
    return "\n".join(lines)
