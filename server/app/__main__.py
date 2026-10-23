import asyncio
import contextlib
import os

import httpx
import uvicorn

from .db import connect
from .env import env
from .reels.browser import close_shared_browser, scrape_with_shared_browser
from .reels.identify import Batches, create_identifier
from .reels.queue import ReelQueue
from .routes import create_app
from .tmdb import Tmdb


async def main():
    database_url, password, tmdb_key, gemini_key = env('DATABASE_URL', 'LOGIN_PASSWORD', 'TMDB_API_KEY', 'GEMINI_API_KEY')
    # Closes everything opened here, last first, when the server stops.
    async with contextlib.AsyncExitStack() as stack:
        pool = await connect(database_url)
        stack.push_async_callback(pool.close)
        tmdb = Tmdb(tmdb_key)
        stack.push_async_callback(tmdb.aclose)
        gemini = await stack.enter_async_context(httpx.AsyncClient())
        stack.push_async_callback(close_shared_browser)

        scrape = scrape_with_shared_browser(pool)
        identify = create_identifier(gemini_key, tmdb.search, gemini)

        async def find_title(url: str):
            batches = Batches(identify)
            reel = await scrape(url, until=batches.until)
            return reel.model_copy(update={'title': batches.title})

        worker = asyncio.create_task(ReelQueue(pool).work(find_title))

        async def stop_worker():
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker

        stack.push_async_callback(stop_worker)

        # 0.0.0.0 so a phone on the LAN can reach it.
        config = uvicorn.Config(create_app(pool, tmdb, password), host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))
        await uvicorn.Server(config).serve()


asyncio.run(main())
