import asyncio

import asyncpg
from playwright.async_api import Browser, Playwright, async_playwright

from .reel import Reel
from .scrape import LOGIN_HINT, Until, scrape_reel

_playwright: Playwright | None = None
_browser: Browser | None = None
# Launching and closing take turns; the idle close must not race the next job's launch.
_lock = asyncio.Lock()
_idle_close: asyncio.Task | None = None


async def _shared_browser():
    """One Chromium for the whole process, launched on first use and relaunched if it dies."""
    global _playwright, _browser
    if _browser and _browser.is_connected():
        return _browser
    _playwright = _playwright or await async_playwright().start()
    # Containers give /dev/shm only 64 MB, which crashes Chromium's pages; /tmp has room.
    _browser = await _playwright.chromium.launch(args=['--disable-dev-shm-usage'])
    return _browser


async def _close():
    global _playwright, _browser
    async with _lock:
        if _browser:
            await _browser.close()
        if _playwright:
            await _playwright.stop()
        _playwright = _browser = None


async def close_shared_browser():
    if _idle_close:
        _idle_close.cancel()
    await _close()


async def _acquire():
    """The shared browser, with any pending idle close called off."""
    global _idle_close
    if _idle_close:
        _idle_close.cancel()
        _idle_close = None
    async with _lock:
        return await _shared_browser()


def _release(idle_seconds: float):
    """Closes the browser, and the Playwright driver with it, unless it is acquired again within idle_seconds."""
    global _idle_close

    async def close_later():
        global _idle_close
        await asyncio.sleep(idle_seconds)
        # Past the sleep, a new job waits on the lock instead of cancelling a half-done close.
        _idle_close = None
        await _close()

    _idle_close = asyncio.create_task(close_later())


def scrape_with_shared_browser(pool: asyncpg.Pool, idle_minutes: float = 5):
    """Scrapes in the shared browser, in a fresh context per reel holding the saved Instagram session.
    The browser (200-300 MB) closes after idle_minutes without a scrape and relaunches on the next one."""

    async def scrape(url: str, until: Until | None = None) -> Reel:
        storage_state = await pool.fetchval('select storage_state from instagram_session')
        if not storage_state:
            raise RuntimeError(f'No Instagram session saved, {LOGIN_HINT}')
        shared = await _acquire()
        try:
            context = await shared.new_context(storage_state=storage_state)
            try:
                return await scrape_reel(context, url, until=until)
            finally:
                await context.close()
        finally:
            _release(idle_minutes * 60)

    return scrape
