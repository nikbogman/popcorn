import pytest

from watcher.tmdb import Movie, MovieDetails

HEAT = MovieDetails(3, 'Heat', 1995, '/heat.jpg', 'A heist.')


@pytest.fixture(autouse=True)
def movies(tmdb):
    tmdb.movies = [Movie(1, 'Before Sunrise', 1995, '/a.jpg'), Movie(2, 'Before Sunset', 2004, None), HEAT]


async def test_search_returns_tmdb_results_in_order_with_w185_posters(api):
    res = await api.get('/api/search', params={'q': 'before'})
    assert res.status_code == 200
    assert res.json() == [
        {'tmdbId': 1, 'title': 'Before Sunrise', 'year': 1995, 'posterUrl': 'https://image.tmdb.org/t/p/w185/a.jpg'},
        {'tmdbId': 2, 'title': 'Before Sunset', 'year': 2004, 'posterUrl': None},
    ]


async def test_search_needs_a_query(api):
    assert (await api.get('/api/search', params={'q': ' '})).status_code == 400
    assert (await api.get('/api/search')).status_code == 400


async def test_movie_details_come_from_tmdb_with_a_w500_poster_and_the_entry(api):
    res = await api.get('/api/movies/3')
    assert res.status_code == 200
    assert res.json() == {
        'tmdbId': 3,
        'title': 'Heat',
        'year': 1995,
        'posterUrl': 'https://image.tmdb.org/t/p/w500/heat.jpg',
        'overview': 'A heist.',
        'status': None,
        'favourite': False,
        'watchedAt': None,
    }


async def test_movie_details_404_when_tmdb_does_not_know_the_id(api):
    assert (await api.get('/api/movies/99')).status_code == 404


@pytest.mark.parametrize('id', ['abc', '0', '-3'])
async def test_movie_details_need_a_positive_id(api, id):
    assert (await api.get(f'/api/movies/{id}')).status_code == 400


async def test_tmdb_being_down_is_a_502(api, tmdb):
    tmdb.down = True
    assert (await api.get('/api/search', params={'q': 'before'})).status_code == 502
    res = await api.get('/api/movies/3')
    assert res.status_code == 502
    assert res.json() == {'error': 'TMDB is unreachable'}


async def test_movie_routes_need_a_token(client):
    assert (await client.get('/api/search', params={'q': 'before'})).status_code == 401
    assert (await client.get('/api/movies/3')).status_code == 401
