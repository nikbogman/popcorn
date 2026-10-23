import re
from dataclasses import asdict, astuple, dataclass, replace
from datetime import UTC, datetime
from typing import Literal

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from pydantic import StrictBool

from .api import Api
from .tmdb import Movie, MovieSummary, Tmdb, TmdbId, found, to_row

PAGE_SIZE = 30

Status = Literal['to_watch', 'watched']

# collection_entry's columns and their Postgres types.
COLUMNS = {
    'tmdb_id': 'int',
    'title': 'text',
    'year': 'int',
    'poster_path': 'text',
    'status': 'text',
    'added_at': 'timestamptz',
    'watched_at': 'timestamptz',
    'favourite': 'bool',
}

_PLACE = 'select status, added_at, watched_at, favourite from collection_entry where tmdb_id = $1'


def now():
    """The clock every change reads. Tests replace it."""
    return datetime.now(UTC)


class Entry(Api):
    """A movie's place in the Collection. All empty when it isn't in it."""

    status: Status | None
    favourite: bool
    watched_at: datetime | None


@dataclass
class Place:
    """A movie's place in the Collection, as stored. Watched iff watched_at is set; only a Watched movie can be a Favourite."""

    status: Status
    added_at: datetime
    watched_at: datetime | None = None
    favourite: bool = False

    @staticmethod
    def to_watch(at: datetime):
        return Place('to_watch', at)

    @staticmethod
    def watched(current: 'Place | None', at: datetime, favourite=False):
        """Watched at `at`, keeping when it was added if it was already in the Collection."""
        return Place('watched', current.added_at if current else at, at, favourite)

    @staticmethod
    def of(row: asyncpg.Record | None):
        return Place(row['status'], row['added_at'], row['watched_at'], row['favourite']) if row else None


def _entry(place: Place | None):
    if place is None:
        return Entry(status=None, favourite=False, watched_at=None)
    return Entry(status=place.status, favourite=place.favourite, watched_at=place.watched_at)


def _values(movie: Movie, place: Place):
    # The movie is copied in once, never refreshed.
    row = {'tmdb_id': movie.tmdb_id, 'title': movie.title, 'year': movie.year, 'poster_path': movie.poster_path, **asdict(place)}
    return [row[c] for c in COLUMNS]


class Collection:
    """The Status and Favourite rules from CONTEXT.md. Database errors raise."""

    def __init__(self, pool: asyncpg.Pool, tmdb: Tmdb):
        self.pool = pool
        self.tmdb = tmdb

    async def _save(self, conn: asyncpg.Connection, tmdb_id: int, current: Place | None, place: Place):
        """Writes `place` over `current`. None if the movie is new to the Collection and TMDB doesn't know the id."""
        if current:
            await conn.execute(
                'update collection_entry set status = $2, added_at = $3, watched_at = $4, favourite = $5 where tmdb_id = $1',
                tmdb_id,
                *astuple(place),
            )
            return _entry(place)
        movie = await self.tmdb.details(tmdb_id)
        if movie is None:
            return None
        # A concurrent request may have added it meanwhile; the later write wins.
        await conn.execute(
            f'insert into collection_entry ({", ".join(COLUMNS)}) values ($1, $2, $3, $4, $5, $6, $7, $8) on conflict (tmdb_id) do update '
            'set status = excluded.status, added_at = excluded.added_at, watched_at = excluded.watched_at, favourite = excluded.favourite',
            *_values(movie, place),
        )
        return _entry(place)

    async def entry(self, tmdb_id: int) -> Entry:
        return _entry(Place.of(await self.pool.fetchrow(_PLACE, tmdb_id)))

    async def set_status(self, tmdb_id: int, status: Status | None) -> Entry | None:
        """None drops the entry. None back if TMDB doesn't know the id."""
        if status is None:
            await self.pool.execute('delete from collection_entry where tmdb_id = $1', tmdb_id)
            return _entry(None)
        async with self.pool.acquire() as conn, conn.transaction():
            current = Place.of(await conn.fetchrow(f'{_PLACE} for update', tmdb_id))
            if current and current.status == status:
                return _entry(current)
            place = Place.to_watch(now()) if status == 'to_watch' else Place.watched(current, now())
            return await self._save(conn, tmdb_id, current, place)

    async def set_favourite(self, tmdb_id: int, favourite: bool) -> Entry | None:
        """None if TMDB doesn't know the id."""
        async with self.pool.acquire() as conn, conn.transaction():
            current = Place.of(await conn.fetchrow(f'{_PLACE} for update', tmdb_id))
            if current and current.status == 'watched':
                return await self._save(conn, tmdb_id, current, replace(current, favourite=favourite))
            # Not Watched, so there is no Favourite to clear.
            if not favourite:
                return _entry(current)
            # Favouriting a movie that isn't Watched marks it Watched.
            return await self._save(conn, tmdb_id, current, Place.watched(current, now(), True))

    async def add(self, entries: list[tuple[Movie, Place]]) -> int:
        """Adds movies with the places they came with, leaving movies already in the Collection alone. Returns how many were added."""
        rows = [_values(movie, place) for movie, place in entries]
        # One array per column, so any number of rows is one statement.
        arrays = ', '.join(f'${i + 1}::{t}[]' for i, t in enumerate(COLUMNS.values()))
        added = await self.pool.fetch(
            f'insert into collection_entry ({", ".join(COLUMNS)}) select * from unnest({arrays}) on conflict do nothing returning tmdb_id',
            *([r[i] for r in rows] for i in range(len(COLUMNS))),
        )
        return len(added)

    async def all(self):
        """Every entry, oldest added first."""
        return await self.pool.fetch('select * from collection_entry order by added_at, tmdb_id')

    async def page(self, status: Status | None, title='', oldest_first=False, offset=0) -> 'CollectionPage':
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
        assert counts
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
