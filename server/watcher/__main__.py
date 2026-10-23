import asyncio
import os

import uvicorn

from .app import create_app
from .db import connect
from .env import env
from .reels.browser import scrape_with_shared_browser
from .reels.identify import Batches, create_identifier
from .reels.queue import ReelQueue
from .tmdb import Tmdb


async def main():
    e = env('DATABASE_URL', 'LOGIN_PASSWORD', 'TMDB_API_KEY', 'GEMINI_API_KEY')
    pool = await connect(e['DATABASE_URL'])
    tmdb = Tmdb(e['TMDB_API_KEY'])
    scrape = scrape_with_shared_browser(pool)
    identify = create_identifier(e['GEMINI_API_KEY'], tmdb)

    async def find_title(url: str):
        batches = Batches(identify)
        reel = await scrape(url, until=batches.until)
        return reel.model_copy(update={'title': batches.title})

    worker = asyncio.create_task(ReelQueue(pool).work(find_title))  # noqa: F841 - held so it isn't garbage collected
    # 0.0.0.0 so a phone on the LAN can reach it.
    config = uvicorn.Config(create_app(pool, tmdb, e['LOGIN_PASSWORD']), host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))
    await uvicorn.Server(config).serve()


asyncio.run(main())
