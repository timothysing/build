"""FastAPI application exposing the Edulink report endpoint."""

from __future__ import annotations

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import ServiceInfo, Settings
from .conversation import answer_question
from .models import EdulinkReport
from .scraper import collect_report
from .summariser import build_summary
from .utils import now_in_timezone

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Edulink Agent", version="0.1.0")


class ReportResponse(BaseModel):
    """Response schema for the /report endpoint."""

    summary: str
    report: EdulinkReport
    info: ServiceInfo


class ChatRequest(BaseModel):
    """Request payload for conversational queries."""

    question: str


class ChatResponse(BaseModel):
    """Response payload for conversational queries."""

    reply: str
    report: EdulinkReport
    info: ServiceInfo


@app.post("/report", response_model=ReportResponse)
async def generate_report() -> ReportResponse:
    """Generate an Edulink report and return the structured payload."""

    logger.info("Received /report request")
    settings = Settings()
    try:
        report = await collect_report(settings)
        report.summary_text = build_summary(report)
    except Exception as exc:
        logger.exception("Failed to build Edulink report: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    info = ServiceInfo(
        generated_at=now_in_timezone(settings.timezone).isoformat(),
        timezone=settings.timezone,
    )
    logger.info("Successfully generated report")
    return ReportResponse(summary=report.summary_text, report=report, info=info)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Answer a conversational query about the most recent Edulink data."""

    logger.info("Received /chat request: %s", request.question)
    settings = Settings()
    try:
        report = await collect_report(settings)
        report.summary_text = build_summary(report)
    except Exception as exc:
        logger.exception("Failed to build Edulink report for chat: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    reply = answer_question(report, request.question)
    info = ServiceInfo(
        generated_at=now_in_timezone(settings.timezone).isoformat(),
        timezone=settings.timezone,
    )
    return ChatResponse(reply=reply, report=report, info=info)
