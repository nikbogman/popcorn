import csv
import io
from datetime import UTC, datetime

import pytest

from popcorn.csv_io import to_csv
from popcorn.tmdb import Movie, MovieDetails

HEADER = 'TMDB ID,Title,Year,Status,Favourite,Added,Watched'

CSV = '\n'.join(
    [
        HEADER,
        '4,Alien,1979,to_watch,false,2026-01-01T00:00:00.000Z,',
        ',Heat,1995,watched,false,2026-01-01T00:00:00.000Z,2026-02-01T00:00:00.000Z',
        ',Ran,1985,,true,2026-02-02T00:00:00.000Z,',
        ',Nowhere,2000,to_watch,false,,',
        '999,Gone,2001,to_watch,false,,',
        'abc,Typo,2001,to_watch,false,,',
        ',Undated,2001,watched,false,2026-01-01,yesterday',
    ]
)


@pytest.fixture(autouse=True)
def movies(tmdb):
    tmdb.movies = [
        Movie(3, 'Heat', 1995, '/heat.jpg'),
        Movie(30, 'Heat', 1986, None),
        Movie(4, 'Alien', 1979, None),
        Movie(5, 'Ran', 1985, None),
    ]


def upload(api, body: str):
    return api.post('/api/collection/import', content=body, headers={'content-type': 'text/csv'})


def test_quoted_cells_keep_their_commas_quotes_and_line_breaks():
    rows = [['Crouching Tiger, Hidden Dragon', 'two\nlines'], ['The "Best" Film', '']]
    assert list(csv.reader(io.StringIO(to_csv(['Name', 'Note'], rows))))[1:] == rows


async def test_imports_by_tmdb_id_or_else_title_and_year_and_is_safe_to_rerun(api, pool):
    result = {'movies': 7, 'notFound': ['Nowhere (2000)', 'Gone (2001)'], 'invalid': ['Typo (2001)', 'Undated (2001)']}
    assert (await upload(api, CSV)).json() == {**result, 'added': 3}
    assert (await upload(api, CSV)).json() == {**result, 'added': 0}

    day = lambda d: datetime(2026, *d, tzinfo=UTC)  # noqa: E731
    entries = await pool.fetch(
        'select tmdb_id, poster_path, status, favourite, added_at, watched_at from collection_entry order by tmdb_id'
    )
    assert [tuple(e) for e in entries] == [
        (3, '/heat.jpg', 'watched', False, day((1, 1)), day((2, 1))),
        (4, None, 'to_watch', False, day((1, 1)), None),
        # A Favourite is Watched; with no Watched date it was watched when it was added.
        (5, None, 'watched', True, day((2, 2)), day((2, 2))),
    ]


async def test_exports_a_csv_the_import_reads_back(api, pool):
    await upload(api, CSV)
    res = await api.get('/api/collection/export')
    assert res.headers['content-type'].startswith('text/csv')
    assert res.headers['content-disposition'] == 'attachment; filename="popcorn.csv"'
    exported = res.text
    assert exported == '\r\n'.join(
        [
            HEADER,
            '3,Heat,1995,watched,false,2026-01-01T00:00:00.000Z,2026-02-01T00:00:00.000Z',
            '4,Alien,1979,to_watch,false,2026-01-01T00:00:00.000Z,',
            '5,Ran,1985,watched,true,2026-02-02T00:00:00.000Z,2026-02-02T00:00:00.000Z',
            '',
        ]
    )

    await pool.execute('truncate collection_entry')
    await upload(api, exported)
    assert (await api.get('/api/collection/export')).text == exported


async def test_a_csv_in_another_format_is_refused(api):
    res = await upload(api, 'Date,Name,Year,Letterboxd URI\n2026-01-01,Heat,1995,u1\n')
    assert res.status_code == 400
    assert res.json() == {'error': f"The CSV's header must be {HEADER}"}


async def test_reads_a_csv_starting_with_a_byte_order_mark(api):
    res = await api.post('/api/collection/import', content=('﻿' + CSV).encode(), headers={'content-type': 'text/csv'})
    assert res.json()['added'] == 3


async def test_a_csv_that_is_not_utf8_is_refused(api):
    res = await api.post(
        '/api/collection/import', content=CSV.replace('Alien', 'Alién').encode('latin-1'), headers={'content-type': 'text/csv'}
    )
    assert (res.status_code, res.json()) == (400, {'error': 'The CSV must be UTF-8'})


async def test_import_and_export_need_a_token(client, pool):
    assert (await upload(client, CSV)).status_code == 401
    assert (await client.get('/api/collection/export')).status_code == 401
    assert await pool.fetchval('select count(*) from collection_entry') == 0


async def test_the_import_is_a_502_when_tmdb_is_down(api, tmdb):
    tmdb.down = True
    res = await upload(api, CSV)
    assert res.status_code == 502
    assert res.json() == {'error': 'TMDB is unreachable'}


async def test_imports_a_csv_larger_than_one_statement_could_carry(api, tmdb):
    async def any_id(tmdb_id: int):
        return MovieDetails(tmdb_id, f'Film {tmdb_id}', 2000, None)

    tmdb.details = any_id
    n = 9000
    rows = ''.join(f'{i},Film {i},2000,to_watch,false,2026-01-01T00:00:00.000Z,\n' for i in range(1, n + 1))
    res = await upload(api, f'{HEADER}\n{rows}')
    assert res.json() == {'movies': n, 'added': n, 'notFound': [], 'invalid': []}
