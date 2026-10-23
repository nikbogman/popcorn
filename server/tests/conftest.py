import os
import secrets
from datetime import UTC, datetime

import asyncpg
import httpx
import pytest

from app import collection
from app.db import connect
from app.routes import create_app
from app.tmdb import MovieDetails, Tmdb, TmdbUnreachable

PASSWORD = 'correct horse battery'


class FakeTmdb(Tmdb):
    """In-memory stand-in for TMDB. Set `down` to make every call raise TmdbUnreachable."""

    def __init__(self, movies: list | None = None):
        self.movies = movies or []
        self.down = False

    async def search(self, query: str):
        if self.down:
            raise TmdbUnreachable()
        return [m for m in self.movies if query.lower() in m.title.lower()]

    async def details(self, tmdb_id: int):
        if self.down:
            raise TmdbUnreachable()
        m = next((m for m in self.movies if m.tmdb_id == tmdb_id), None)
        return m and MovieDetails(m.tmdb_id, m.title, m.year, m.poster_path, getattr(m, 'overview', ''))


@pytest.fixture(scope='session')
async def pool():
    """The app's tables in a throwaway schema of TEST_DATABASE_URL, dropped after the run."""
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.exit('Set TEST_DATABASE_URL to a Postgres the tests may create a schema in')
    schema = f'test_{secrets.token_hex(4)}'
    admin = await asyncpg.connect(url)
    await admin.execute(f'create schema {schema}')
    pool = await connect(url, server_settings={'search_path': schema})
    yield pool
    await pool.close()
    await admin.execute(f'drop schema {schema} cascade')
    await admin.close()


@pytest.fixture(autouse=True)
async def _empty(request):
    # Only tests that touch the database pay for the truncate.
    if 'pool' in request.fixturenames:
        db = request.getfixturevalue('pool')
        await db.execute('truncate collection_entry, reel_scrape, auth_token, instagram_session')


@pytest.fixture
def tmdb():
    return FakeTmdb()


@pytest.fixture
async def client(pool, tmdb):
    """The app with no token."""
    transport = httpx.ASGITransport(create_app(pool, tmdb, PASSWORD), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as c:
        yield c


@pytest.fixture
async def api(client):
    """The app, signed in."""
    res = await client.post('/api/auth/login', json={'password': PASSWORD})
    assert res.status_code == 200
    client.headers['authorization'] = f'Bearer {res.json()["token"]}'
    return client


class Clock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, 10, tzinfo=UTC)


@pytest.fixture
def clock(monkeypatch):
    """Fixes the time collection changes are stamped with. Set clock.now to move it."""
    c = Clock()
    monkeypatch.setattr(collection, 'now', lambda: c.now)
    return c
