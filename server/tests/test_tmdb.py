import httpx
import pytest

from app.tmdb import Movie, MovieDetails, Tmdb, TmdbUnreachable


def stub(body=None, status=200, raw: str | None = None):
    urls: list[str] = []

    def handle(request: httpx.Request):
        urls.append(str(request.url))
        return httpx.Response(status, text=raw) if raw is not None else httpx.Response(status, json=body or {})

    return Tmdb('KEY', httpx.MockTransport(handle)), urls


async def test_search_maps_results_to_poster_paths_dropping_adult_titles():
    tmdb, urls = stub(
        {
            'results': [
                {'id': 1, 'title': 'Heat', 'release_date': '1995-12-15', 'poster_path': '/heat.jpg', 'adult': False},
                {'id': 2, 'title': 'Unknown', 'release_date': '', 'poster_path': None, 'adult': False},
                {'id': 3, 'title': 'Adult', 'release_date': '2000-01-01', 'poster_path': None, 'adult': True},
            ]
        }
    )
    assert await tmdb.search('heat') == [Movie(1, 'Heat', 1995, '/heat.jpg'), Movie(2, 'Unknown', None, None)]
    assert 'include_adult=false' in urls[0]
    assert 'api_key=KEY' in urls[0]


async def test_details_maps_a_movie():
    tmdb, urls = stub({'id': 1, 'title': 'Heat', 'release_date': '1995-12-15', 'poster_path': '/heat.jpg', 'overview': 'A heist.'})
    assert await tmdb.details(1) == MovieDetails(1, 'Heat', 1995, '/heat.jpg', 'A heist.')
    assert '/movie/1?' in urls[0]


async def test_details_is_none_for_an_unknown_id():
    assert await stub(status=404)[0].details(1) is None


@pytest.mark.parametrize(
    'tmdb',
    [stub(status=500)[0], stub(raw='<html>')[0], stub({})[0]],
    ids=['error status', 'not json', 'missing fields'],
)
async def test_tmdb_failures_are_unreachable(tmdb):
    with pytest.raises(TmdbUnreachable):
        await tmdb.search('heat')
    with pytest.raises(TmdbUnreachable):
        await tmdb.details(1)


async def test_a_network_failure_is_unreachable():
    def offline(request):
        raise httpx.ConnectError('down')

    with pytest.raises(TmdbUnreachable):
        await Tmdb('KEY', httpx.MockTransport(offline)).search('heat')
