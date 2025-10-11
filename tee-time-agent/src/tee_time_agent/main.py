"""Entry point for the tee time agent."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date as date_type
from typing import List, Optional

import structlog
from google.adk.runners import InMemoryRunner
from google.genai import types

from .adk_agent import TeeTimeAgent
from .config import Settings
from .date_window import TargetDate, compute_target_dates


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structlog + stdlib logging."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stdout,
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.EventRenamer("event"),
            structlog.processors.DictRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


LOGGER = structlog.get_logger(__name__)


async def run(settings: Settings, targets: List[TargetDate]) -> None:
    """Execute the ADK workflow for the given targets."""
    agent = TeeTimeAgent(
        name="tee_time_agent",
        description="Collects BRS tee sheet availability and posts to Telegram.",
        settings=settings,
        targets=targets,
    )

    async with InMemoryRunner(agent=agent, app_name="tee-time-agent") as runner:
        user_id = settings.environment or "tee-time"
        session_id = "tee-time-session"

        await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id,
        )

        trigger = types.Content(
            role="user",
            parts=[types.Part.from_text("Run tee sheet check")],
        )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=trigger,
        ):
            LOGGER.info(
                "agent.event",
                author=event.author,
                text=_extract_event_text(event),
            )


def parse_args() -> argparse.Namespace:
    """CLI argument parsing."""
    parser = argparse.ArgumentParser(description="Fetch BRS tee sheet availability and push to Telegram.")
    parser.add_argument(
        "--force-date",
        type=str,
        help="ISO date (YYYY-MM-DD) to scrape regardless of 10-day rule.",
    )
    return parser.parse_args()


def resolve_targets(force_date: Optional[str]) -> List[TargetDate]:
    """Determine which dates to inspect."""
    if force_date:
        try:
            forced_value = date_type.fromisoformat(force_date)
        except ValueError as exc:
            raise SystemExit(f"Invalid --force-date: {force_date}") from exc
        return [TargetDate(forced_value)]
    return compute_target_dates()


def cli() -> None:
    """Console script entrypoint."""
    args = parse_args()
    configure_logging()

    try:
        settings = Settings()
    except Exception as exc:  # pragma: no cover - startup validation
        LOGGER.exception("settings.error", error=str(exc))
        raise SystemExit(2) from exc

    targets = resolve_targets(args.force_date)

    try:
        asyncio.run(run(settings, targets))
    except Exception as exc:  # pragma: no cover - top level
        LOGGER.exception("agent.failed", error=str(exc))
        raise SystemExit(1) from exc


def _extract_event_text(event) -> str:
    """Extract human-readable text from an ADK event."""
    if event.content and event.content.parts:
        fragments = [part.text for part in event.content.parts if getattr(part, "text", None)]
        return " ".join(fragment for fragment in fragments if fragment)
    return ""
