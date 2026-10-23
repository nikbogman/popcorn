from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import APIRouter, HTTPException, Path

from .api import Api
from .tmdb import Movie, Tmdb

if TYPE_CHECKING:
    from .collection import Collection

IMAGES = 'https://image.tmdb.org/t/p'
SIZES = {'row': 'w185', 'page': 'w500'}

Status = Literal['to_watch', 'watched']

TmdbId = Annotated[int, Path(gt=0, description='A TMDB movie id')]


def poster_url(path: str | None, use: Literal['row', 'page']):
    return f'{IMAGES}/{SIZES[use]}{path}' if path else None


class MovieSummary(Api):
    """A list or search row as the app receives it."""

    tmdb_id: int
    title: str
    year: int | None
    poster_url: str | None


class Entry(Api):
    """A movie's place in the Collection. All empty when it isn't in it."""

    status: Status | None
    favourite: bool
    watched_at: datetime | None


class MoviePage(MovieSummary, Entry):
    overview: str


def to_row(m: Movie):
    return MovieSummary(tmdb_id=m.tmdb_id, title=m.title, year=m.year, poster_url=poster_url(m.poster_path, 'row'))


def found[T](result: T | None) -> T:
    """Unwraps a TMDB-backed result: None (unknown id) is a 404."""
    if result is None:
        raise HTTPException(404, 'Movie not found')
    return result


def movie_routes(tmdb: Tmdb, collection: Collection):
    router = APIRouter()

    @router.get('/search')
    async def search(q: str) -> list[MovieSummary]:
        if not q.strip():
            raise HTTPException(400, 'q is required')
        return [to_row(m) for m in await tmdb.search(q.strip())]

    @router.get('/movies/{tmdb_id}')
    async def movie(tmdb_id: TmdbId) -> MoviePage:
        m = found(await tmdb.details(tmdb_id))
        entry = await collection.entry(tmdb_id)
        return MoviePage(
            tmdb_id=m.tmdb_id,
            title=m.title,
            year=m.year,
            poster_url=poster_url(m.poster_path, 'page'),
            overview=m.overview,
            **dict(entry),
        )

    return router
