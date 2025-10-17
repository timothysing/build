"""Command-line entry point for the Edulink agent."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Optional

from .config import Settings
from .conversation import answer_question
from .scraper import collect_report
from .summariser import build_summary

logger = logging.getLogger(__name__)


def cli(argv: Optional[list[str]] = None) -> int:
    """Run the agent either in summary or conversational mode."""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Edulink automation agent")
    parser.add_argument(
        "--ask",
        dest="question",
        help="Ask a question about homework, behaviour or mailbox instead of printing the daily summary.",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    try:
        report = asyncio.run(collect_report(settings))
        report.summary_text = build_summary(report)
    except Exception as exc:
        logger.exception("Failed to collect Edulink report: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.question:
        response = answer_question(report, args.question)
        print(response)
    else:
        print(report.summary_text)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli())
