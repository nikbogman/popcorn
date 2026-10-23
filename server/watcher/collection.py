import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from pydantic import StrictBool

from .api import Api
from .movies import Entry, MovieSummary, Status, TmdbId, found, to_row
from .tmdb import Movie, Tmdb

PAGE_SIZE = 30


def now():
    """The clock every change reads. Tests replace it."""
    return datetime.now(UTC)


@dataclass
class NewEntry:
    """A movie arriving with its history, e.g. from an import.
    Watched if watched_at is set, else To watch; only a Watched movie can be a Favourite."""

    movie: Movie
    added_at: datetime
    watched_at: datetime | None
    favourite: bool


def _entry(row: dict | None):
    return Entry(
        status=row['status'] if row else None,
        favourite=row['favourite'] if row else False,
        watched_at=row['watched_at'] if row else None,
    )


def _to_watch(at: datetime):
    return {'status': 'to_watch', 'added_at': at, 'watched_at': None, 'favourite': False}


def _watched(current: dict | None, at: datetime, favourite=False):
    return {'status': 'watched', 'added_at': current['added_at'] if current else at, 'watched_at': at, 'favourite': favourite}


def _row(movie: Movie, entry: dict):
    # The movie is copied in once, never refreshed.
    return {'tmdb_id': movie.tmdb_id, 'title': movie.title, 'year': movie.year, 'poster_path': movie.poster_path, **entry}


COLUMNS = ['tmdb_id', 'title', 'year', 'poster_path', 'status', 'added_at', 'watched_at', 'favourite']
TYPES = ['int', 'text', 'int', 'text', 'text', 'timestamptz', 'timestamptz', 'bool']


class Collection:
    """The Status and Favourite rules from CONTEXT.md. Database errors raise."""

    def __init__(self, pool: asyncpg.Pool, tmdb: Tmdb):
        self.pool = pool
        self.tmdb = tmdb

    async def _find(self, tmdb_id: int):
        row = await self.pool.fetchrow('select * from collection_entry where tmdb_id = $1', tmdb_id)
        return dict(row) if row else None

    async def _drop(self, tmdb_id: int):
        await self.pool.execute('delete from collection_entry where tmdb_id = $1', tmdb_id)
        return _entry(None)

    async def _update(self, tmdb_id: int, entry: dict):
        await self.pool.execute(
            'update collection_entry set status = $2, added_at = $3, watched_at = $4, favourite = $5 where tmdb_id = $1',
            tmdb_id,
            entry['status'],
            entry['added_at'],
            entry['watched_at'],
            entry['favourite'],
        )
        return _entry(entry)

    async def _create(self, tmdb_id: int, entry: dict):
        """None if TMDB doesn't know the id."""
        movie = await self.tmdb.details(tmdb_id)
        if movie is None:
            return None
        await self.add_rows([_row(movie, entry)])
        return _entry(entry)

    async def entry(self, tmdb_id: int):
        return _entry(await self._find(tmdb_id))

    async def set_status(self, tmdb_id: int, status: Status | None):
        """None drops the entry."""
        if status is None:
            return await self._drop(tmdb_id)
        current = await self._find(tmdb_id)
        if current and current['status'] == status:
            return _entry(current)
        nxt = _to_watch(now()) if status == 'to_watch' else _watched(current, now())
        return await self._update(tmdb_id, nxt) if current else await self._create(tmdb_id, nxt)

    async def set_favourite(self, tmdb_id: int, favourite: bool):
        current = await self._find(tmdb_id)
        if current and current['status'] == 'watched':
            return await self._update(tmdb_id, {**current, 'favourite': favourite})
        # Not Watched, so there is no Favourite to clear.
        if not favourite:
            return _entry(current)
        # Favouriting a movie that isn't Watched marks it Watched.
        nxt = _watched(current, now(), True)
        return await self._update(tmdb_id, nxt) if current else await self._create(tmdb_id, nxt)

    async def add_rows(self, rows: list[dict]):
        """Inserts rows, leaving movies already in the Collection alone. Returns how many were added."""
        # One array per column, so any number of rows is one statement.
        arrays = ', '.join(f'${i + 1}::{t}[]' for i, t in enumerate(TYPES))
        added = await self.pool.fetch(
            f'insert into collection_entry ({", ".join(COLUMNS)}) select * from unnest({arrays}) on conflict do nothing returning tmdb_id',
            *([r[c] for r in rows] for c in COLUMNS),
        )
        return len(added)

    async def add(self, entries: list[NewEntry]):
        """Adds movies with the dates they came with, leaving movies already in the Collection alone. Returns how many were added."""
        return await self.add_rows(
            [
                _row(
                    e.movie,
                    {'status': 'watched', 'added_at': e.added_at, 'watched_at': e.watched_at, 'favourite': e.favourite}
                    if e.watched_at
                    else _to_watch(e.added_at),
                )
                for e in entries
            ]
        )

    async def all(self):
        """Every entry, oldest added first."""
        return await self.pool.fetch('select * from collection_entry order by added_at, tmdb_id')

    async def page(self, status: Status | None, title='', oldest_first=False, offset=0):
        """
        A Status's movies, or with status None the Favourites. Newest first unless oldest_first.
        `total` counts the whole list, `matching` only the titles containing `title`.
        """
        where = '(status = $1::text or $1::text is null and favourite)'
        # To watch sorts by when a movie was added, Watched and Favourites by when it was watched.
        date = 'added_at' if status == 'to_watch' else 'watched_at'
        direction = 'asc' if oldest_first else 'desc'
        search = f"{where} and title ilike '%' || $2 || '%'"
        pattern = re.sub(r'[\\%_]', r'\\\g<0>', title)
        counts = await self.pool.fetchrow(
            f'select count(*) total, count(*) filter (where {search}) matching from collection_entry where {where}', status, pattern
        )
        # tmdb_id breaks date ties so pages never overlap.
        rows = await self.pool.fetch(
            f'select * from collection_entry where {search} order by {date} {direction}, tmdb_id {direction} limit $3 offset $4',
            status,
            pattern,
            PAGE_SIZE,
            offset,
        )
        nxt = offset + len(rows)
        return CollectionPage(
            movies=[to_row(Movie(r['tmdb_id'], r['title'], r['year'], r['poster_path'])) for r in rows],
            total=counts['total'],
            matching=counts['matching'],
            next_offset=nxt if nxt < counts['matching'] else None,
        )


class CollectionPage(Api):
    movies: list[MovieSummary]
    total: int
    matching: int
    next_offset: int | None


class StatusChange(Api):
    status: Status | None


class FavouriteChange(Api):
    favourite: StrictBool


def collection_routes(collection: Collection):
    router = APIRouter()

    @router.get('')
    async def list_collection(
        status: Status | None = None,
        favourite: Literal['true'] | None = None,
        title: str = '',
        order: Literal['newest', 'oldest'] = 'newest',
        offset: int = Query(0, ge=0),
    ) -> CollectionPage:
        """To watch and Watched filter by status, Favourites by favourite=true."""
        if (status is None) == (favourite is None):
            raise HTTPException(400, 'filter by favourite=true or status, one of to_watch, watched')
        return await collection.page(status, title.strip(), order == 'oldest', offset)

    @router.put('/{tmdb_id}/status')
    async def set_status(change: StatusChange, tmdb_id: TmdbId) -> Entry:
        return found(await collection.set_status(tmdb_id, change.status))

    @router.put('/{tmdb_id}/favourite')
    async def set_favourite(change: FavouriteChange, tmdb_id: TmdbId) -> Entry:
        return found(await collection.set_favourite(tmdb_id, change.favourite))

    return router
