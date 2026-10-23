from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from app.collection import PAGE_SIZE, Collection
from app.tmdb import Movie

DAY1 = '2026-01-01T10:00:00Z'
DAY2 = datetime(2026, 1, 2, 10, tzinfo=UTC)
DAY3 = datetime(2026, 1, 3, 10, tzinfo=UTC)


@pytest.fixture(autouse=True)
def movies(tmdb, clock):
    tmdb.movies = [Movie(3, 'Heat', 1995, '/heat.jpg'), Movie(4, 'Alien', 1979, None), Movie(5, 'Ran', 1985, '/ran.jpg')]


async def change(api, tmdb_id: int, change: dict):
    return await api.put(f'/api/collection/{tmdb_id}/{"status" if "status" in change else "favourite"}', json=change)


async def entry(api, tmdb_id: int):
    m = (await api.get(f'/api/movies/{tmdb_id}')).json()
    return {k: m[k] for k in ('status', 'favourite', 'watchedAt')}


async def ids(res):
    return [m['tmdbId'] for m in res.json()['movies']]


def listing(api, query: str):
    return api.get(f'/api/collection?{query}')


NOT_IN_COLLECTION = {'status': None, 'favourite': False, 'watchedAt': None}
TO_WATCH_ENTRY = {'status': 'to_watch', 'favourite': False, 'watchedAt': None}
WATCHED_ENTRY = {'status': 'watched', 'favourite': False, 'watchedAt': DAY1}
FAVOURITE_ENTRY = {**WATCHED_ENTRY, 'favourite': True}

TO_WATCH = {'status': 'to_watch'}
WATCHED = {'status': 'watched'}
DROP = {'status': None}
FAVOURITE = {'favourite': True}
UNFAVOURITE = {'favourite': False}

# (entry reached by these changes, change, expected entry)
RULES = [
    ([], TO_WATCH, TO_WATCH_ENTRY),
    ([], WATCHED, WATCHED_ENTRY),
    ([], DROP, NOT_IN_COLLECTION),
    ([], FAVOURITE, FAVOURITE_ENTRY),
    ([], UNFAVOURITE, NOT_IN_COLLECTION),
    ([TO_WATCH], TO_WATCH, TO_WATCH_ENTRY),
    ([TO_WATCH], WATCHED, WATCHED_ENTRY),
    ([TO_WATCH], DROP, NOT_IN_COLLECTION),
    ([TO_WATCH], FAVOURITE, FAVOURITE_ENTRY),
    ([TO_WATCH], UNFAVOURITE, TO_WATCH_ENTRY),
    ([WATCHED], TO_WATCH, TO_WATCH_ENTRY),
    ([WATCHED], WATCHED, WATCHED_ENTRY),
    ([WATCHED], DROP, NOT_IN_COLLECTION),
    ([WATCHED], FAVOURITE, FAVOURITE_ENTRY),
    ([WATCHED], UNFAVOURITE, WATCHED_ENTRY),
    ([FAVOURITE], TO_WATCH, TO_WATCH_ENTRY),
    ([FAVOURITE], WATCHED, FAVOURITE_ENTRY),
    ([FAVOURITE], DROP, NOT_IN_COLLECTION),
    ([FAVOURITE], FAVOURITE, FAVOURITE_ENTRY),
    ([FAVOURITE], UNFAVOURITE, WATCHED_ENTRY),
]


@pytest.mark.parametrize(('setup', 'step', 'expected'), RULES)
async def test_status_and_favourite_rules(api, setup, step, expected):
    for s in setup:
        assert (await change(api, 3, s)).status_code == 200
    res = await change(api, 3, step)
    assert res.status_code == 200
    assert res.json() == expected
    assert await entry(api, 3) == expected


@pytest.mark.parametrize('step', [WATCHED, FAVOURITE, UNFAVOURITE])
async def test_changes_to_a_watched_movie_keep_the_watched_date(api, clock, step):
    await change(api, 3, WATCHED)
    clock.now = DAY2
    await change(api, 3, step)
    assert (await entry(api, 3))['watchedAt'] == DAY1


async def test_to_watch_lists_newest_added_first_from_the_stored_copy(api, tmdb, clock):
    await change(api, 3, TO_WATCH)
    clock.now = DAY2
    await change(api, 4, TO_WATCH)
    await change(api, 5, WATCHED)
    tmdb.down = True
    res = await listing(api, 'status=to_watch')
    assert res.status_code == 200
    assert res.json() == {
        'movies': [
            {'tmdbId': 4, 'title': 'Alien', 'year': 1979, 'posterUrl': None},
            {'tmdbId': 3, 'title': 'Heat', 'year': 1995, 'posterUrl': 'https://image.tmdb.org/t/p/w185/heat.jpg'},
        ],
        'total': 2,
        'matching': 2,
        'nextOffset': None,
    }


async def test_watched_lists_newest_watched_date_first(api, clock):
    await change(api, 3, TO_WATCH)
    await change(api, 4, WATCHED)
    clock.now = DAY2
    await change(api, 5, WATCHED)
    clock.now = DAY3
    await change(api, 3, WATCHED)
    assert await ids(await listing(api, 'status=watched')) == [3, 5, 4]


async def test_favourites_lists_newest_watched_date_first_from_the_stored_copy(api, tmdb, clock):
    await change(api, 3, WATCHED)
    clock.now = DAY2
    await change(api, 4, FAVOURITE)
    clock.now = DAY3
    await change(api, 5, FAVOURITE)
    await change(api, 3, FAVOURITE)
    tmdb.down = True
    assert await ids(await listing(api, 'favourite=true')) == [5, 4, 3]


@pytest.mark.parametrize('step', [UNFAVOURITE, TO_WATCH, DROP])
async def test_changes_that_take_a_movie_off_favourites(api, step):
    await change(api, 3, FAVOURITE)
    await change(api, 3, step)
    assert await ids(await listing(api, 'favourite=true')) == []


async def test_a_movie_moved_back_from_watched_counts_as_newly_added(api, clock):
    await change(api, 3, WATCHED)
    await change(api, 4, TO_WATCH)
    clock.now = DAY2
    await change(api, 3, TO_WATCH)
    assert await ids(await listing(api, 'status=to_watch')) == [3, 4]


async def test_lists_come_in_pages_that_pick_up_where_the_last_ended(api, pool):
    count = PAGE_SIZE + 5
    start = datetime(2026, 1, 1, tzinfo=UTC)
    # Every other pair shares a date, so pages rely on the tie-break.
    await pool.executemany(
        "insert into collection_entry (tmdb_id, title, status, added_at, favourite) values ($1, $2, 'to_watch', $3, false)",
        [(100 + i, f'Movie {i}', start + timedelta(seconds=i // 2)) for i in range(count)],
    )
    first = (await listing(api, 'status=to_watch')).json()
    assert (first['total'], first['matching'], first['nextOffset'], len(first['movies'])) == (count, count, PAGE_SIZE, PAGE_SIZE)
    rest = (await listing(api, f'status=to_watch&offset={first["nextOffset"]}')).json()
    assert (rest['total'], rest['nextOffset']) == (count, None)
    assert len({m['tmdbId'] for m in first['movies'] + rest['movies']}) == count


async def test_order_oldest_lists_oldest_first(api, clock):
    await change(api, 3, TO_WATCH)
    clock.now = DAY2
    await change(api, 4, TO_WATCH)
    assert await ids(await listing(api, 'status=to_watch&order=oldest')) == [3, 4]


async def test_title_keeps_matching_titles_and_counts_both(api):
    for tmdb_id in (3, 4, 5):
        await change(api, tmdb_id, TO_WATCH)
    res = (await listing(api, 'status=to_watch&title=%20aLi%20')).json()
    assert (res['total'], res['matching'], res['nextOffset']) == (3, 1, None)
    assert [m['tmdbId'] for m in res['movies']] == [4]
    assert await ids(await listing(api, 'status=to_watch&title=%25')) == []


@pytest.mark.parametrize('query', ['order=sideways', 'offset=-1', 'offset=two'])
async def test_a_page_needs_a_valid_query(api, query):
    assert (await listing(api, f'status=to_watch&{query}')).status_code == 400


@pytest.mark.parametrize('query', ['status=someday', 'favourite=false', 'favourite=true&status=watched', ''])
async def test_the_collection_needs_a_known_filter(api, query):
    assert (await listing(api, query)).status_code == 400


@pytest.mark.parametrize('step', [TO_WATCH, FAVOURITE])
async def test_creating_an_entry_for_an_unknown_movie_is_a_404(api, step):
    assert (await change(api, 99, step)).status_code == 404


@pytest.mark.parametrize('step', [TO_WATCH, FAVOURITE])
async def test_creating_an_entry_while_tmdb_is_down_is_a_502(api, tmdb, step):
    tmdb.down = True
    assert (await change(api, 3, step)).status_code == 502


async def test_changing_an_existing_entry_does_not_need_tmdb(api, tmdb):
    await change(api, 3, TO_WATCH)
    tmdb.down = True
    assert (await change(api, 3, WATCHED)).status_code == 200


@pytest.mark.parametrize('step', [DROP, UNFAVOURITE])
async def test_clearing_a_movie_not_in_the_collection_does_not_need_tmdb(api, tmdb, step):
    tmdb.down = True
    assert (await change(api, 99, step)).status_code == 200


@pytest.mark.parametrize(
    ('field', 'body'), [('status', {'status': 'favourite'}), ('status', {}), ('favourite', {'favourite': 'yes'}), ('favourite', {})]
)
async def test_a_change_needs_a_valid_body(api, field, body):
    assert (await api.put(f'/api/collection/3/{field}', json=body)).status_code == 400


async def test_collection_routes_need_a_token(client):
    assert (await client.put('/api/collection/3/status', json=TO_WATCH)).status_code == 401
    assert (await client.put('/api/collection/3/favourite', json=FAVOURITE)).status_code == 401
    assert (await client.get('/api/collection?status=to_watch')).status_code == 401


async def test_a_database_failure_is_a_500_not_a_tmdb_error(api, monkeypatch):
    async def broken(*args):
        raise asyncpg.PostgresError('connection lost')

    monkeypatch.setattr(Collection, '_save', broken)
    res = await change(api, 3, TO_WATCH)
    assert res.status_code == 500
    assert res.json() == {'error': 'Internal error'}
