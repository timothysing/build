"""Custom ADK agent that orchestrates tee sheet collection and messaging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncGenerator, List

import structlog
from google.adk.agents.base_agent import BaseAgent
from google.adk.events.event import Event
from google.genai import types
from pydantic import Field

from .config import Settings
from .date_window import TargetDate
from .ollama_client import OllamaClient
from .playwright_client import TeeSheetBrowser, TeeSheetSnapshot
from .telegram import format_message, post_to_telegram

LOGGER = structlog.get_logger(__name__)


@dataclass
class SnapshotRecord:
    """Container linking a target date to its captured tee sheet snapshot."""

    target: TargetDate
    snapshot: TeeSheetSnapshot


class TeeTimeAgent(BaseAgent):
    """Agent that gathers tee sheets, summarises them, and notifies Telegram."""

    settings: Settings
    targets: List[TargetDate] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        """Initialise internal helpers after pydantic validation."""
        super().model_post_init(__context)  # type: ignore[misc]
        self._ollama = OllamaClient(self.settings)

    async def _run_async_impl(
        self, ctx
    ) -> AsyncGenerator[Event, None]:
        """Run the agent end-to-end."""
        if not self.targets:
            yield self._text_event(
                ctx,
                "No target dates fall on Friday/Saturday/Sunday 10 days ahead. Exiting.",
                final=True,
            )
            return

        snapshots: list[SnapshotRecord] = []

        try:
            async with TeeSheetBrowser(self.settings) as browser:
                for target in self.targets:
                    url = self.settings.tee_sheet_url(target.value)
                    try:
                        snapshot = await browser.snapshot_for_date(
                            date_iso=target.iso,
                            day_name=target.day_name,
                            url=url,
                        )
                        snapshots.append(SnapshotRecord(target=target, snapshot=snapshot))
                        yield self._text_event(
                            ctx,
                            f"Fetched tee sheet for {target.day_name} {target.iso}.",
                        )
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.exception(
                            "agent.fetch_failed",
                            target_date=target.iso,
                            error=str(exc),
                        )
                        yield self._text_event(
                            ctx,
                            f"Failed to fetch tee sheet for {target.day_name} {target.iso}: {exc}",
                        )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("agent.browser_error", error=str(exc))
            yield self._text_event(
                ctx,
                f"Playwright session failed: {exc}",
                final=True,
            )
            return

        if not snapshots:
            yield self._text_event(
                ctx,
                "No tee sheets captured successfully. See previous logs for details.",
                final=True,
            )
            return

        delivered: list[str] = []
        failures: list[str] = []

        for record in snapshots:
            target = record.target
            snapshot = record.snapshot
            try:
                analysis = await self._ollama.analyse_snapshot(snapshot)
                yield self._text_event(
                    ctx,
                    f"Analysed tee sheet for {target.day_name} {target.iso}: {analysis.summary}",
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception(
                    "agent.ollama_failed",
                    target_date=target.iso,
                    error=str(exc),
                )
                failures.append(f"Ollama analysis failed for {target.iso}: {exc}")
                yield self._text_event(
                    ctx,
                    f"Ollama analysis failed for {target.day_name} {target.iso}: {exc}",
                )
                continue

            message = format_message(analysis)

            try:
                await post_to_telegram(self.settings, message)
                delivered.append(target.iso)
                yield self._text_event(
                    ctx,
                    f"Telegram update sent for {target.day_name} {target.iso}.",
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception(
                    "agent.telegram_failed",
                    target_date=target.iso,
                    error=str(exc),
                )
                failures.append(f"Telegram send failed for {target.iso}: {exc}")
                yield self._text_event(
                    ctx,
                    f"Telegram send failed for {target.day_name} {target.iso}: {exc}",
                )

        summary_lines = [
            f"Delivery summary — succeeded: {len(delivered)}, failed: {len(failures)}."
        ]
        if delivered:
            summary_lines.append(f"Delivered dates: {', '.join(sorted(delivered))}.")
        if failures:
            summary_lines.append("Failures:")
            summary_lines.extend(f"- {item}" for item in failures)

        yield self._text_event(ctx, "\n".join(summary_lines), final=True)

    def _text_event(self, ctx, text: str, *, final: bool = False) -> Event:
        """Create a simple text event for the ADK runner."""
        content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=text)],
        )
        event = Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=content,
        )
        if final:
            event.actions.end_of_agent = True
        return event
