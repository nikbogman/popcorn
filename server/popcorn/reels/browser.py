import asyncpg
from playwright.async_api import Browser, Playwright, async_playwright

from .reel import Reel
from .scrape import LOGIN_HINT, Until, scrape_reel

_playwright: Playwright | None = None
_browser: Browser | None = None


async def _shared_browser():
    """One Chromium for the whole process, launched on first use and relaunched if it dies."""
    global _playwright, _browser
    if _browser and _browser.is_connected():
        return _browser
    _playwright = _playwright or await async_playwright().start()
    # Containers give /dev/shm only 64 MB, which crashes Chromium's pages; /tmp has room.
    _browser = await _playwright.chromium.launch(args=['--disable-dev-shm-usage'])
    return _browser


async def close_shared_browser():
    global _playwright, _browser
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()
    _playwright = _browser = None


def scrape_with_shared_browser(pool: asyncpg.Pool):
    """Scrapes in the shared browser, in a fresh context per reel holding the saved Instagram session."""

    async def scrape(url: str, until: Until | None = None) -> Reel:
        storage_state = await pool.fetchval('select storage_state from instagram_session')
        if not storage_state:
            raise RuntimeError(f'No Instagram session saved, {LOGIN_HINT}')
        context = await (await _shared_browser()).new_context(storage_state=storage_state)
        try:
            return await scrape_reel(context, url, until=until)
        finally:
            await context.close()

    return scrape
