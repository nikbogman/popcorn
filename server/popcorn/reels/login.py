"""Saves the Instagram session the scraper uses. Pass a storage-state JSON file to import it instead of logging in."""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from ..db import connect
from ..env import env


async def main():
    [database_url] = env('DATABASE_URL')
    pool = await connect(database_url)
    if len(sys.argv) > 1:
        storage_state = json.loads(Path(sys.argv[1]).read_text())  # noqa: ASYNC240 - a one-shot script, nothing else is running
    else:
        # Log in by hand in the window. Saved as soon as Instagram sets its session cookie.
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto('https://www.instagram.com/accounts/login/')
            print('Log in to Instagram in the browser window…')
            while not any(c['name'] == 'sessionid' for c in await context.cookies()):
                await page.wait_for_timeout(1000)
            storage_state = await context.storage_state()
            await browser.close()

    await pool.execute(
        """insert into instagram_session (storage_state) values ($1)
        on conflict (id) do update set storage_state = excluded.storage_state, saved_at = now()""",
        storage_state,
    )
    print('Instagram session saved')
    await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
