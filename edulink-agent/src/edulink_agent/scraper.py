"""Playwright scraping logic for Edulink."""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import suppress
from datetime import date
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Browser, Page, Playwright, TimeoutError as PlaywrightTimeoutError, async_playwright

from .config import Settings
from .models import BehaviourEntry, EdulinkReport, HomeworkItem, MailEntry
from .utils import normalise_whitespace, now_in_timezone, parse_date, yesterday

logger = logging.getLogger(__name__)


LOGIN_USERNAME_SELECTOR = "input[name='username'], input#username, input[placeholder*='username' i]"
LOGIN_PASSWORD_SELECTOR = "input[type='password'], input#password"
LOGIN_SUBMIT_SELECTOR = "button[type='submit'], button:has-text('Log in'), button:has-text('Login')"
SCHOOL_INPUT_SELECTOR = "input[name='institution'], input#institution, input[placeholder*='school' i]"


async def collect_report(settings: Settings) -> EdulinkReport:
    """Main entry point that orchestrates the scraping workflow."""

    tz_name = settings.timezone
    generated_at = now_in_timezone(tz_name)
    target_date = yesterday(tz_name)

    async with async_playwright() as playwright:
        browser = await _launch_browser(playwright, settings.headless)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            await _login(page, settings)
            homework = await _collect_homework(page, settings)
            total_points, behaviour_entries = await _collect_behaviour(page, settings, target_date)
            mailbox_entries = await _collect_mail(page, settings, target_date)
        finally:
            await browser.close()

    return EdulinkReport(
        generated_at=generated_at,
        timezone=tz_name,
        child_name=settings.child_name,
        total_achievement_points=total_points,
        homework_outstanding=homework,
        behaviour_new=behaviour_entries,
        mailbox_new=mailbox_entries,
        summary_text="",  # filled in by the summariser later
    )


async def _launch_browser(playwright: Playwright, headless: bool) -> Browser:
    """Launch Chromium with sensible defaults."""
    logger.info("Launching Chromium headless=%s", headless)
    return await playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )


async def _login(page: Page, settings: Settings) -> None:
    """Handle the Edulink login workflow."""

    logger.info("Navigating to login page")
    await page.goto(f"{settings.base_url}/#!/login", wait_until="domcontentloaded")

    if settings.school_code:
        logger.info("Filling school code")
        with suppress(PlaywrightTimeoutError):
            school_input = await page.wait_for_selector(SCHOOL_INPUT_SELECTOR, timeout=settings.timeout_seconds * 1000)
            await school_input.fill(settings.school_code)
            await asyncio.sleep(0.5)
            with suppress(PlaywrightTimeoutError):
                await page.click("button:has-text('Next')")
                await page.wait_for_timeout(500)

    logger.info("Submitting credentials for %s", settings.username)
    try:
        username_input = await page.wait_for_selector(LOGIN_USERNAME_SELECTOR, timeout=settings.timeout_seconds * 1000)
        password_input = await page.wait_for_selector(LOGIN_PASSWORD_SELECTOR, timeout=settings.timeout_seconds * 1000)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("Unable to locate login form elements on Edulink") from exc

    await username_input.fill(settings.username)
    await password_input.fill(settings.password.get_secret_value())
    await page.click(LOGIN_SUBMIT_SELECTOR)
    await page.wait_for_timeout(2000)

    # Verify login by checking for a navigation item visible after authentication.
    with suppress(PlaywrightTimeoutError):
        await page.wait_for_selector("nav, a[href*='homework'], .menu", timeout=settings.timeout_seconds * 1000)


async def _collect_homework(page: Page, settings: Settings) -> List[HomeworkItem]:
    """Return outstanding homework items."""

    url = f"{settings.base_url}/#!/homework/list"
    logger.info("Fetching homework list %s", url)
    await page.goto(url, wait_until="domcontentloaded")
    await _stabilise(page)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_with_header(soup, required=("submission",))

    if not table:
        logger.warning("Homework table not found; returning empty list")
        return []

    header_map = _map_table_headers(table)
    items: List[HomeworkItem] = []

    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        values = [normalise_whitespace(cell.get_text()) for cell in cells]
        submission = _value_for_header(values, header_map, ("submission",))
        if submission and "not" in submission.lower():
            item = HomeworkItem(
                subject=_value_for_header(values, header_map, ("subject", "class")),
                title=_value_for_header(values, header_map, ("title", "description", "homework")),
                set_by=_value_for_header(values, header_map, ("teacher", "staff", "set by")),
                due_date=parse_date(_value_for_header(values, header_map, ("due", "deadline")) or ""),
                submission_status=submission,
                details=_value_for_header(values, header_map, ("details", "notes")),
            )
            items.append(item)

    logger.info("Found %s outstanding homework entries", len(items))
    return items


async def _collect_behaviour(page: Page, settings: Settings, target_date: date) -> tuple[Optional[int], List[BehaviourEntry]]:
    """Return behaviour summary (total points + entries for the specified date)."""

    url = f"{settings.base_url}/#!/behaviour/summary/points/achievement"
    logger.info("Fetching behaviour summary %s", url)
    await page.goto(url, wait_until="domcontentloaded")
    await _stabilise(page)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    total_points = _extract_total_achievement_points(soup)

    table = _find_table_with_header(soup, required=("date", "points"))
    if not table:
        logger.warning("Behaviour entries table not found")
        return total_points, []

    header_map = _map_table_headers(table)
    entries: List[BehaviourEntry] = []

    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        values = [normalise_whitespace(cell.get_text()) for cell in cells]
        entry_date = parse_date(_value_for_header(values, header_map, ("date",)))
        if entry_date != target_date:
            continue
        points_text = _value_for_header(values, header_map, ("points", "score"))
        try:
            points = int(points_text) if points_text is not None else None
        except ValueError:
            points = None

        entry = BehaviourEntry(
            date=entry_date,
            category=_value_for_header(values, header_map, ("type", "category")),
            points=points,
            description=_value_for_header(values, header_map, ("description", "reason", "details")),
            staff=_value_for_header(values, header_map, ("staff", "teacher")),
        )
        entries.append(entry)

    logger.info("Found %s behaviour entries for %s", len(entries), target_date)
    return total_points, entries


async def _collect_mail(page: Page, settings: Settings, target_date: date) -> List[MailEntry]:
    """Return communicator mailbox entries for the specified date."""

    url = f"{settings.base_url}/#!/communicator/mailbox"
    logger.info("Fetching communicator mailbox %s", url)
    await page.goto(url, wait_until="domcontentloaded")

    # Ensure the "Received" tab is active.
    with suppress(Exception):
        await page.click("button:has-text('Received'), a:has-text('Received')")
        await page.wait_for_timeout(500)

    await _stabilise(page)

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_with_header(soup, required=("date", "subject"))
    if not table:
        logger.warning("Mailbox table not found")
        return []

    header_map = _map_table_headers(table)
    entries: List[MailEntry] = []

    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        values = [normalise_whitespace(cell.get_text()) for cell in cells]
        entry_date = parse_date(_value_for_header(values, header_map, ("date", "received")))
        if entry_date != target_date:
            continue
        entry = MailEntry(
            date=entry_date,
            sender=_value_for_header(values, header_map, ("from", "sender")),
            subject=_value_for_header(values, header_map, ("subject", "title")),
            summary=_value_for_header(values, header_map, ("summary", "message", "content")),
        )
        entries.append(entry)

    logger.info("Found %s mailbox entries for %s", len(entries), target_date)
    return entries


async def _stabilise(page: Page) -> None:
    """Wait for network traffic to idle, ignoring timeouts."""

    with suppress(Exception):
        await page.wait_for_load_state("networkidle", timeout=4000)
    await page.wait_for_timeout(500)


def _find_table_with_header(soup: BeautifulSoup, required: tuple[str, ...]) -> Optional[Tag]:
    """Return the first table that contains all required headers."""

    required_normalised = {h.lower() for h in required}
    for table in soup.find_all("table"):
        header_map = _map_table_headers(table)
        if required_normalised.issubset(set(header_map.keys())):
            return table
    return None


def _map_table_headers(table: Tag) -> Dict[str, int]:
    """Map normalised header names to their column index."""

    mapping: Dict[str, int] = {}
    headers = table.select("thead th")
    if not headers:
        headers = table.select("tr th")

    for idx, header in enumerate(headers):
        text = normalise_whitespace(header.get_text()).lower()
        if not text:
            continue
        mapping[text] = idx
    return mapping


def _value_for_header(values: List[str], header_map: Dict[str, int], aliases: tuple[str, ...]) -> Optional[str]:
    """Return the first matching value for the provided header aliases."""

    for alias in aliases:
        alias_lower = alias.lower()
        for header, idx in header_map.items():
            if alias_lower == header or alias_lower in header:
                if 0 <= idx < len(values):
                    value = values[idx].strip()
                    if value:
                        return value
    return None


def _extract_total_achievement_points(soup: BeautifulSoup) -> Optional[int]:
    """Extract the achievement points total from the behaviour page."""

    # Look for obvious numeric summaries.
    text = soup.get_text(" ", strip=True)
    match = re.search(r"(total\s+achievement\s+points|achievement\s+points)\D*(\d+)", text, flags=re.IGNORECASE)
    if match:
        try:
            return int(match.group(2))
        except ValueError:
            pass

    # As a fallback, search for green labels.
    for element in soup.find_all(["span", "div"], attrs={"class": re.compile("green", re.IGNORECASE)}):
        with suppress(ValueError):
            return int(element.get_text(strip=True))
    return None
