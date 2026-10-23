import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Literal

import asyncpg
from fastapi import APIRouter, HTTPException

from ..api import Api
from .reel import Reel, Title
from .scrape import shortcode_of

# Scrapes one reel. The queue's only dependency on a browser.
Scrape = Callable[[str], Awaitable[Reel]]

JobStatus = Literal['queued', 'running', 'done', 'failed']

# GET /api/reels returns the newest this many.
LIST_LIMIT = 100


class ReelRequest(Api):
    """A reel shared to the app, with its title instead of the whole reel."""

    id: uuid.UUID
    url: str
    status: JobStatus
    title: Title | None
    error: str | None
    created_at: datetime


class Job(Api):
    """A scrape's status and, once done or failed, its reel or error."""

    status: JobStatus
    reel: Reel | None
    error: str | None


class ReelQueue:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def run_next(self, scrape: Scrape):
        """One worker step: claims the oldest queued job and runs it. False when the queue is empty."""
        job = await self.pool.fetchrow(
            """update reel_scrape set status = 'running', updated_at = now()
            where id = (select id from reel_scrape where status = 'queued' order by created_at limit 1 for update skip locked)
            returning id, url"""
        )
        if not job:
            return False
        try:
            reel = await scrape(job['url'])
            await self.pool.execute(
                "update reel_scrape set status = 'done', reel = $2, updated_at = now() where id = $1",
                job['id'],
                reel.model_dump(by_alias=True),
            )
        except Exception as e:
            await self.pool.execute(
                "update reel_scrape set status = 'failed', error = $2, updated_at = now() where id = $1", job['id'], str(e)
            )
        return True

    async def retry(self, id: uuid.UUID) -> bool:
        """Queues a failed scrape again. False when there is no failed scrape with that id."""
        return bool(
            await self.pool.fetchval(
                "update reel_scrape set status = 'queued', error = null, updated_at = now() "
                "where id = $1 and status = 'failed' returning true",
                id,
            )
        )

    async def enqueue(self, url: str) -> uuid.UUID | None:
        """Queues a scrape. Returns its id, or None when the URL isn't an Instagram reel or post."""
        shortcode = shortcode_of(url)
        if not shortcode:
            return None
        # One scrape per reel: sharing it again moves it to the top of the list, and re-queues it if it failed.
        return await self.pool.fetchval(
            """insert into reel_scrape (url) values ($1)
            on conflict (url) do update set
              created_at = now(),
              updated_at = now(),
              status = case when reel_scrape.status = 'failed' then 'queued' else reel_scrape.status end,
              error = case when reel_scrape.status = 'failed' then null else reel_scrape.error end
            returning id""",
            f'https://www.instagram.com/p/{shortcode}/',
        )

    async def list(self) -> list[ReelRequest]:
        """The newest LIST_LIMIT scrapes, newest shared first."""
        rows = await self.pool.fetch(
            "select id, url, status, reel->'title' title, error, created_at from reel_scrape order by created_at desc limit $1", LIST_LIMIT
        )
        return [ReelRequest.model_validate(dict(r)) for r in rows]

    async def job(self, id: uuid.UUID) -> Job | None:
        """None for an unknown id."""
        row = await self.pool.fetchrow('select status, reel, error from reel_scrape where id = $1', id)
        return Job.model_validate(dict(row)) if row else None

    async def work(self, scrape: Scrape):
        """Runs jobs one at a time, forever, polling every 2s when idle."""
        # ponytail: assumes one server process, so anything still running was cut off by a restart.
        # Running several would need a lease (locked_at) instead.
        await self.pool.execute("update reel_scrape set status = 'queued' where status = 'running'")
        while True:
            try:
                ran = await self.run_next(scrape)
            except Exception:
                logging.exception('Reel worker')
                ran = False
            if not ran:
                await asyncio.sleep(2)


class ReelUrl(Api):
    url: str


class Queued(Api):
    id: uuid.UUID


def reel_routes(queue: ReelQueue):
    """POST a reel URL to queue a scrape, then poll GET /{id} until its status is done or failed. GET lists the newest."""
    router = APIRouter()

    @router.post('', status_code=202)
    async def share(body: ReelUrl) -> Queued:
        id = await queue.enqueue(body.url)
        if not id:
            raise HTTPException(400, 'url must be an Instagram reel or post URL')
        return Queued(id=id)

    @router.get('')
    async def requests() -> list[ReelRequest]:
        return await queue.list()

    @router.post('/{id}/retry', status_code=202)
    async def retry(id: uuid.UUID) -> None:
        if not await queue.retry(id):
            raise HTTPException(404, 'No failed scrape with that id')

    @router.get('/{id}')
    async def job(id: uuid.UUID) -> Job:
        job = await queue.job(id)
        if not job:
            raise HTTPException(404, 'Scrape not found')
        return job

    return router
