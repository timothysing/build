"""Telegram messaging helper."""

from __future__ import annotations

import httpx
import structlog

from .config import Settings
from .models import TeeSheetAnalysis, TeeTimeSlot

LOGGER = structlog.get_logger(__name__)


def format_message(analysis: TeeSheetAnalysis) -> str:
    """Build a human-friendly message for Telegram."""
    lines: list[str] = [
        f"{analysis.day_name} ({analysis.date_iso})",
        analysis.summary,
        "",
    ]

    if analysis.tee_times:
        lines.append("Tee times:")
        for slot in analysis.tee_times:
            lines.append(f"- {format_slot(slot)}")
    else:
        lines.append("No tee times parsed.")

    if analysis.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in analysis.warnings:
            lines.append(f"- {warning}")

    lines.append("")
    lines.append(f"Source: {analysis.source_url}")
    lines.append(f"(Model: {analysis.model_used})")

    return "\n".join(lines).strip()


def format_slot(slot: TeeTimeSlot) -> str:
    """Format a single tee time slot for Telegram."""
    pieces = [slot.time, slot.status]
    if slot.available_slots is not None:
        label = "slot" if slot.available_slots == 1 else "slots"
        pieces.append(f"{slot.available_slots} {label}")
    if slot.notes:
        pieces.append(slot.notes)
    if slot.is_bookable and "book" not in slot.status.lower():
        pieces.append("Bookable")
    return " — ".join(pieces)


async def post_to_telegram(settings: Settings, text: str) -> None:
    """Send the composed message to Telegram."""
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    url = f"{settings.telegram_api_endpoint}/sendMessage"
    LOGGER.info("telegram.send.start", url=url)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload)
    if response.is_success:
        LOGGER.info("telegram.send.success")
        return
    LOGGER.error("telegram.send.failed", status_code=response.status_code, body=response.text)
    raise RuntimeError(f"Telegram send failed with {response.status_code}: {response.text}")
