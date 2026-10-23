import functools
from dataclasses import dataclass

import httpx

API = 'https://api.themoviedb.org/3'


@dataclass
class Movie:
    """A movie as the server holds it: the poster is a path, sized only when a response is shaped."""

    tmdb_id: int
    title: str
    year: int | None
    poster_path: str | None


@dataclass
class MovieDetails(Movie):
    overview: str = ''


class TmdbUnreachable(Exception):
    """What every TMDB call raises when TMDB can't be reached or errors. The app answers it with a 502."""

    def __init__(self):
        super().__init__('TMDB is unreachable')


def _unreachable(call):
    # Network errors, error statuses and bodies that aren't what TMDB documents all mean TMDB can't serve us.
    @functools.wraps(call)
    async def wrapped(*args, **kwargs):
        try:
            return await call(*args, **kwargs)
        except TmdbUnreachable:
            raise
        except Exception as e:
            raise TmdbUnreachable() from e

    return wrapped


def _year(date: str | None):
    # TMDB sends "" for an unknown release date.
    return int(date[:4]) if date else None


class Tmdb:
    """Both calls raise TmdbUnreachable when TMDB can't be reached."""

    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None):
        self._client = httpx.AsyncClient(base_url=API, params={'api_key': api_key}, transport=transport, timeout=10)

    async def _get(self, path: str, **params) -> dict | None:
        res = await self._client.get(path, params=params)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    @_unreachable
    async def search(self, query: str) -> list[Movie]:
        body = await self._get('/search/movie', query=query, include_adult='false')
        return [Movie(m['id'], m['title'], _year(m.get('release_date')), m['poster_path']) for m in body['results'] if not m.get('adult')]

    @_unreachable
    async def details(self, tmdb_id: int) -> MovieDetails | None:
        """None when TMDB doesn't know the id."""
        m = await self._get(f'/movie/{tmdb_id}')
        if m is None:
            return None
        return MovieDetails(m['id'], m['title'], _year(m.get('release_date')), m['poster_path'], m.get('overview') or '')
