"""Wrapper around the Ollama HTTP API used for tee sheet summarisation."""

from __future__ import annotations

import json
import textwrap
from typing import Any, Optional

import httpx
import structlog
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential

from .config import Settings
from .models import TeeSheetAnalysis, TeeTimeSlot
from .playwright_client import TeeSheetSnapshot

LOGGER = structlog.get_logger(__name__)


class OllamaClient:
    """Helper for interacting with an Ollama model."""

    def __init__(self, settings: Settings):
        self._settings = settings

    async def analyse_snapshot(self, snapshot: TeeSheetSnapshot) -> TeeSheetAnalysis:
        """Invoke the Ollama model to interpret the tee sheet snapshot."""
        prompt = self._build_prompt(snapshot)
        payload = {
            "model": self._settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
            },
        }

        LOGGER.info(
            "ollama.request.start",
            model=self._settings.ollama_model,
            date_iso=snapshot.date_iso,
        )

        try:
            response_json = await self._invoke_generate(payload)
        except RetryError as exc:
            raise RuntimeError("Failed communicating with Ollama after retries") from exc

        raw_text = str(response_json.get("response", "")).strip()
        LOGGER.debug(
            "ollama.response",
            preview=raw_text[:200],
            total_length=len(raw_text),
        )

        parsed = self._parse_response(raw_text)

        tee_times = [
            TeeTimeSlot(
                time=str(item.get("time", "")).strip(),
                status=str(item.get("status", "")).strip(),
                available_slots=self._coerce_int(item.get("available_slots")),
                is_bookable=bool(item.get("is_bookable", False)),
                notes=(item.get("notes") or None),
            )
            for item in parsed.get("tee_times", [])
            if item.get("time")
        ]

        warnings = [
            str(message).strip()
            for message in parsed.get("warnings", [])
            if str(message).strip()
        ]

        summary = parsed.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = self._fallback_summary(tee_times, warnings, snapshot)

        return TeeSheetAnalysis(
            date_iso=snapshot.date_iso,
            day_name=snapshot.day_name,
            summary=summary.strip(),
            tee_times=tee_times,
            warnings=warnings,
            source_url=snapshot.url,
            model_used=f"ollama:{self._settings.ollama_model}",
            model_raw_response=raw_text,
        )

    async def _invoke_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute the Ollama generate call with retry behaviour."""
        async for attempt in AsyncRetrying(
            wait=wait_exponential(multiplier=1, min=1, max=8),
            stop=stop_after_attempt(3),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(
                    base_url=str(self._settings.ollama_base_url),
                    timeout=60.0,
                ) as client:
                    response = await client.post("/api/generate", json=payload)
                    response.raise_for_status()
                    return response.json()
        raise RuntimeError("Ollama generate invocation failed")  # safety net

    def _build_prompt(self, snapshot: TeeSheetSnapshot) -> str:
        """Construct the prompt sent to the Ollama model."""
        truncated_html = snapshot.html_fragment
        if len(truncated_html) > 30_000:
            truncated_html = truncated_html[:30_000]

        truncated_text = snapshot.text_fragment
        if len(truncated_text) > 20_000:
            truncated_text = truncated_text[:20_000]

        return textwrap.dedent(
            f"""
            You are an assistant that extracts tee time availability from BRS Golf
            tee sheet markup. Only respond with valid JSON matching this schema:
            {{
              "summary": string,
              "tee_times": [
                {{
                  "time": "HH:MM",
                  "status": string,
                  "available_slots": integer | null,
                  "is_bookable": boolean,
                  "notes": string | null
                }}
              ],
              "warnings": [string, ...]
            }}

            Requirements:
            - Keep "summary" under 160 characters.
            - Include tee times that look bookable or notable; omit completed slots.
            - Use warnings for login problems, competitions, or unexpected layouts.
            - If no tee times are visible, return an empty list and explain in summary.

            Context:
            - Date: {snapshot.date_iso} ({snapshot.day_name})
            - Source URL: {snapshot.url}

            Tee sheet HTML:
            ```html
            {truncated_html}
            ```

            Tee sheet visible text:
            ```
            {truncated_text}
            ```
            """
        ).strip()

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        """Best-effort integer coercion."""
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_response(raw_text: str) -> dict[str, Any]:
        """Extract JSON from the Ollama model response."""
        candidate = raw_text.strip()
        if not candidate:
            return {}

        if "```" in candidate:
            parts = candidate.split("```")
            if len(parts) >= 3:
                candidate = parts[1]
            else:
                candidate = parts[-1]
        candidate = candidate.strip()

        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            LOGGER.warning("ollama.json_decode_failed")
            return {}

    @staticmethod
    def _fallback_summary(
        tee_times: list[TeeTimeSlot],
        warnings: list[str],
        snapshot: TeeSheetSnapshot,
    ) -> str:
        """Fallback summary when the model response is incomplete."""
        if not tee_times:
            if warnings:
                return f"No tee times parsed for {snapshot.day_name} {snapshot.date_iso}; warnings: {warnings[0]}"
            return f"No tee times parsed for {snapshot.day_name} {snapshot.date_iso}."
        bookable = [slot for slot in tee_times if slot.is_bookable]
        if bookable:
            return f"{len(bookable)} bookable tee time(s) found for {snapshot.day_name} {snapshot.date_iso}."
        return f"Tee sheet analysed for {snapshot.day_name} {snapshot.date_iso}; no bookable slots identified."
