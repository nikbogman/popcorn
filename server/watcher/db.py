import json
from pathlib import Path

import asyncpg

MIGRATIONS = Path(__file__).parent / 'migrations'


async def _codecs(conn: asyncpg.Connection):
    # jsonb in and out as Python values rather than strings.
    await conn.set_type_codec('jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')


async def connect(url: str, **kwargs) -> asyncpg.Pool:
    """A pool over a migrated database. If Postgres isn't up yet this throws, and Docker's restart policy retries."""
    pool = await asyncpg.create_pool(url, init=_codecs, **kwargs)
    await migrate(pool)
    return pool


async def migrate(pool: asyncpg.Pool):
    """Runs each migrations/*.sql not yet recorded, in name order, each in its own transaction."""
    async with pool.acquire() as conn:
        await conn.execute(
            'create table if not exists schema_migration (name text primary key, applied_at timestamptz not null default now())'
        )
        done = {r['name'] for r in await conn.fetch('select name from schema_migration')}
        for file in sorted(MIGRATIONS.glob('*.sql')):
            if file.name in done:
                continue
            async with conn.transaction():
                await conn.execute(file.read_text())
                await conn.execute('insert into schema_migration (name) values ($1)', file.name)
