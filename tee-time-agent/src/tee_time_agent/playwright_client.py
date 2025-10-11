"""Playwright automation for the BRS member portal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog
from playwright.async_api import Browser, Page, async_playwright

from .config import Settings

LOGGER = structlog.get_logger(__name__)


@dataclass
class TeeSheetSnapshot:
    """HTML/inner text captured for a specific tee sheet."""

    url: str
    date_iso: str
    day_name: str
    html_fragment: str
    text_fragment: str


class TeeSheetBrowser:
    """Helper that manages a logged-in Playwright session."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> "TeeSheetBrowser":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._settings.headless)
        context = await self._browser.new_context()
        self._page = await context.new_page()
        await self._login()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._page:
            await self._page.context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _login(self) -> None:
        """Log into the BRS member portal."""
        if not self._page:
            raise RuntimeError("Playwright page has not been initialised")

        LOGGER.info("login.start", url=self._settings.login_url)
        await self._page.goto(str(self._settings.login_url), wait_until="domcontentloaded")
        await self._page.wait_for_timeout(500)

        await self._page.fill('input[name="login_form[username]"]', self._settings.brs_username)
        await self._page.fill(
            'input[name="login_form[password]"]',
            self._settings.brs_password.get_secret_value(),
        )
        await self._page.click('button[name="login_form[login]"], button[type="submit"]')
        await self._page.wait_for_load_state("networkidle", timeout=self._settings.timeout_seconds * 1000)

        # If we are still on the login page after submitting, treat it as a failure.
        if "login" in self._page.url.lower():
            LOGGER.error("login.failed", current_url=self._page.url)
            raise RuntimeError("Login failed - still on login page after submission")

        LOGGER.info("login.complete", redirected_to=self._page.url)

    async def snapshot_for_date(self, *, date_iso: str, day_name: str, url: str) -> TeeSheetSnapshot:
        """Navigate to a tee sheet and capture the key markup."""
        if not self._page:
            raise RuntimeError("Playwright page has not been initialised")

        LOGGER.info("teesheet.load.start", url=url, date_iso=date_iso)
        await self._page.goto(url, wait_until="domcontentloaded", timeout=self._settings.timeout_seconds * 1000)
        await self._page.wait_for_load_state("networkidle", timeout=self._settings.timeout_seconds * 1000)

        # Allow time for the client-side Vue app to render the table before we scrape it.
        await self._page.wait_for_timeout(750)

        table_locator = self._page.locator("table.border-collapse")
        if await table_locator.count() == 0:
            LOGGER.warning("teesheet.table_missing", url=url)
            html_fragment = await self._page.content()
            text_fragment = await self._page.locator("main").inner_text(timeout=1000)
        else:
            table = table_locator.nth(0)
            html_fragment = await table.inner_html()
            text_fragment = await table.inner_text()

        LOGGER.info("teesheet.load.success", url=url, date_iso=date_iso)

        return TeeSheetSnapshot(
            url=url,
            date_iso=date_iso,
            day_name=day_name,
            html_fragment=html_fragment,
            text_fragment=text_fragment,
        )
