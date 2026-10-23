import json
import os

import httpx
import pytest

from popcorn.reels.identify import Batches, create_identifier
from popcorn.reels.queue import ReelQueue
from popcorn.reels.reel import Comment, Reel, Title
from popcorn.tmdb import Movie

URL = 'https://www.instagram.com/reel/DNBbfSkMPuy/'
COMMENT = Comment(author='someone', text='what movie is this?', likes=3, created_at='2026-10-04T00:00:00.000Z')
REEL = Reel(url=URL, description='Son of the White Mare', comments=[COMMENT])
REEL_JSON = {
    'url': URL,
    'description': 'Son of the White Mare',
    'comments': [{'author': 'someone', 'text': 'what movie is this?', 'likes': 3, 'createdAt': '2026-10-04T00:00:00.000Z'}],
    'title': None,
}
HEAT = Title(name='Heat', year=1995, kind='movie', tmdb_id=949)


@pytest.fixture
def queue(pool):
    return ReelQueue(pool)


async def share(api, url=URL):
    return (await api.post('/api/reels', json={'url': url})).json()['id']


async def poll(api, id: str):
    return (await api.get(f'/api/reels/{id}')).json()


def scraping(reel=REEL, scraped: list | None = None):
    async def scrape(url: str):
        if scraped is not None:
            scraped.append(url)
        return reel.model_copy(update={'url': url})

    return scrape


async def failing(url: str):
    raise RuntimeError('Instagram session expired')


async def test_reel_routes_need_a_token(client):
    assert (await client.post('/api/reels', json={'url': URL})).status_code == 401
    assert (await client.get('/api/reels/00000000-0000-0000-0000-000000000000')).status_code == 401


@pytest.mark.parametrize('url', ['https://www.instagram.com/nasa/', 'https://example.com/reel/abc123/', 42])
async def test_rejects_a_url_that_is_not_an_instagram_reel_or_post(api, url):
    assert (await api.post('/api/reels', json={'url': url})).status_code == 400


async def test_queues_a_reel_then_a_worker_run_stores_its_scrape(api, queue):
    id = await share(api)
    assert await poll(api, id) == {'status': 'queued', 'reel': None, 'error': None}

    scraped = []
    assert await queue.run_next(scraping(scraped=scraped)) is True
    # Stored as the /p/ link, the one the scraper opens.
    assert scraped == ['https://www.instagram.com/p/DNBbfSkMPuy/']
    assert await poll(api, id) == {'status': 'done', 'reel': {**REEL_JSON, 'url': scraped[0]}, 'error': None}


async def test_records_why_a_scrape_failed(api, queue):
    id = await share(api)
    await queue.run_next(failing)
    assert await poll(api, id) == {'status': 'failed', 'reel': None, 'error': 'Instagram session expired'}


async def test_runs_jobs_oldest_first_one_per_run_and_reports_an_empty_queue(api, queue):
    first = await share(api, 'https://www.instagram.com/p/first/')
    second = await share(api, 'https://www.instagram.com/p/second/')
    scraped = []
    await queue.run_next(scraping(scraped=scraped))
    assert (await poll(api, second))['status'] == 'queued'
    await queue.run_next(scraping(scraped=scraped))
    assert await queue.run_next(scraping()) is False
    assert scraped == ['https://www.instagram.com/p/first/', 'https://www.instagram.com/p/second/']
    assert (await poll(api, first))['status'] == 'done'


async def test_lists_every_request_newest_first_with_its_title_once_identified(api, queue):
    first = await share(api, 'https://www.instagram.com/p/first/')
    await queue.run_next(scraping(REEL.model_copy(update={'title': HEAT})))
    second = await share(api, 'https://www.instagram.com/p/second/')

    requests = (await api.get('/api/reels')).json()
    assert [{k: r[k] for k in ('id', 'url', 'status', 'title', 'error')} for r in requests] == [
        {'id': second, 'url': 'https://www.instagram.com/p/second/', 'status': 'queued', 'title': None, 'error': None},
        {
            'id': first,
            'url': 'https://www.instagram.com/p/first/',
            'status': 'done',
            'title': {'name': 'Heat', 'year': 1995, 'kind': 'movie', 'tmdbId': 949},
            'error': None,
        },
    ]
    assert isinstance(requests[0]['createdAt'], str)
    assert 'reel' not in requests[1]


async def test_sharing_the_same_reel_again_returns_its_request_moved_to_the_top(api):
    id = await share(api, 'https://www.instagram.com/reel/DNBbfSkMPuy/?igsh=abc')
    await share(api, 'https://www.instagram.com/p/other/')
    assert await share(api, 'https://www.instagram.com/p/DNBbfSkMPuy/') == id
    ids = [r['id'] for r in (await api.get('/api/reels')).json()]
    assert (ids[0], len(ids)) == (id, 2)


async def test_sharing_a_failed_reel_again_requeues_it(api, queue):
    id = await share(api)
    await queue.run_next(failing)
    assert await share(api) == id
    assert await poll(api, id) == {'status': 'queued', 'reel': None, 'error': None}


async def test_retries_a_failed_request_and_only_a_failed_one(api, queue):
    id = await share(api)
    assert (await api.post(f'/api/reels/{id}/retry')).status_code == 404
    await queue.run_next(failing)
    assert (await api.post(f'/api/reels/{id}/retry')).status_code == 202
    assert await poll(api, id) == {'status': 'queued', 'reel': None, 'error': None}
    assert (await api.post('/api/reels/not-a-uuid/retry')).status_code == 400


async def test_404s_an_unknown_scrape(api):
    assert (await api.get('/api/reels/00000000-0000-0000-0000-000000000000')).status_code == 404
    assert (await api.get('/api/reels/not-a-uuid')).status_code == 400


# Identifying


async def search_heat(query: str):
    return [Movie(2, 'Heat', 1986, None), Movie(949, 'Heat', 1995, None)]


def gemini(answer: dict | None = None, status=200):
    sent: list[dict] = []

    def handle(request: httpx.Request):
        sent.append(json.loads(request.content))
        if status != 200:
            return httpx.Response(status, text='quota exceeded')
        return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(answer)}]}}]})

    return create_identifier('KEY', search_heat, httpx.AsyncClient(transport=httpx.MockTransport(handle))), sent


TWO_COMMENTS = Reel(
    url=URL,
    description='best ending ever',
    comments=[
        Comment(author='a', text='what movie?', likes=1, created_at='2026-10-04T00:00:00.000Z'),
        Comment(author='b', text='Heat (1995), Mann at his best', likes=40, created_at='2026-10-04T00:00:00.000Z'),
    ],
)


async def test_matches_a_movie_to_tmdb_by_year_prompting_with_the_most_liked_comments_first():
    identify, sent = gemini({'found': True, 'name': 'Heat', 'year': 1995, 'kind': 'movie'})
    assert await identify(TWO_COMMENTS) == HEAT
    text = sent[0]['contents'][0]['parts'][0]['text']
    assert text.index('Heat (1995)') < text.index('what movie?')


async def test_keeps_geminis_answer_unmatched_when_no_tmdb_result_has_its_year():
    identify, _ = gemini({'found': True, 'name': 'Heat', 'year': 2013, 'kind': 'movie'})
    assert await identify(TWO_COMMENTS) == Title(name='Heat', year=2013, kind='movie', tmdb_id=None)


async def test_raises_when_gemini_errors_so_the_scrape_job_fails():
    identify, _ = gemini(status=429)
    with pytest.raises(RuntimeError, match='Gemini failed with 429'):
        await identify(TWO_COMMENTS)


async def test_a_tv_show_has_no_tmdb_match():
    identify, _ = gemini({'found': True, 'name': 'Severance', 'year': 2022, 'kind': 'tv'})
    assert await identify(TWO_COMMENTS) == Title(name='Severance', year=2022, kind='tv', tmdb_id=None)


async def test_none_when_the_reel_does_not_say_what_it_shows():
    identify, _ = gemini({'found': False, 'name': '', 'year': None, 'kind': 'movie'})
    assert await identify(TWO_COMMENTS) is None


def comments(n: int):
    return REEL.model_copy(update={'comments': [COMMENT.model_copy(update={'text': f'c{i}'}) for i in range(n)]})


def fake_identify(names=lambda texts: False):
    """Names HEAT when `names` accepts the batch's comment texts; records each batch it was asked about."""
    asked: list[list[str]] = []

    async def identify(reel: Reel):
        texts = [c.text for c in reel.comments]
        asked.append(texts)
        return HEAT if names(texts) else None

    return identify, asked


async def test_batches_ask_about_the_caption_alone_first_and_stop_there_when_it_names_the_title():
    identify, asked = fake_identify(lambda texts: True)
    batches = Batches(identify, 20)
    assert await batches.until(comments(15), False) is True
    assert asked == [[]]
    assert batches.title == HEAT


async def test_batches_then_ask_about_each_full_batch_and_stop_at_the_one_that_names_the_title():
    identify, asked = fake_identify(lambda texts: 'c25' in texts)
    batches = Batches(identify, 20)
    assert await batches.until(comments(15), False) is False
    assert await batches.until(comments(30), False) is False
    assert await batches.until(comments(45), False) is True
    assert [(b[0] if b else None, len(b)) for b in asked] == [(None, 0), ('c0', 20), ('c20', 20)]
    assert batches.title == HEAT


async def test_batches_ask_about_the_leftover_comments_when_the_scrape_ends():
    identify, asked = fake_identify()
    batches = Batches(identify, 20)
    await batches.until(comments(25), False)
    await batches.until(comments(25), True)
    assert [len(b) for b in asked] == [0, 20, 5]
    assert batches.title is None


async def test_batches_skip_the_caption_question_when_there_is_no_caption():
    identify, asked = fake_identify()
    await Batches(identify, 20).until(comments(20).model_copy(update={'description': None}), False)
    assert [len(b) for b in asked] == [20]


async def test_batches_do_not_ask_again_when_the_comments_end_on_a_full_batch():
    identify, asked = fake_identify()
    batches = Batches(identify, 20)
    await batches.until(comments(20), False)
    await batches.until(comments(20), True)
    assert [len(b) for b in asked] == [0, 20]


# Live: scrapes Instagram with a session file exported by Playwright (e.g. from `context.storage_state()`).
# Set INSTAGRAM_SESSION_FILE to run. Replace the reel if it disappears.
SESSION = os.environ.get('INSTAGRAM_SESSION_FILE')
LIVE_REEL = 'https://www.instagram.com/p/DNBbfSkMPuy/'


@pytest.fixture
async def scrape():
    from playwright.async_api import async_playwright

    from popcorn.reels.scrape import scrape_reel

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        async def run(url: str, max_comments=200):
            context = await browser.new_context(storage_state=SESSION)
            try:
                return await scrape_reel(context, url, max_comments)
            finally:
                await context.close()

        yield run
        await browser.close()


live = pytest.mark.skipif(not SESSION, reason='set INSTAGRAM_SESSION_FILE to scrape Instagram')


@live
async def test_scrapes_the_description_and_comments_of_a_live_reel(scrape):
    reel = await scrape(LIVE_REEL)
    assert reel.url == LIVE_REEL
    assert 'Son of the White Mare' in reel.description
    assert reel.comments
    assert all(c.author and c.likes >= 0 and c.created_at > '2010' for c in reel.comments)


@live
async def test_gets_comments_from_a_reel_link_which_opens_the_comment_less_viewer(scrape):
    assert len((await scrape('https://www.instagram.com/reel/DNBbfSkMPuy/', 5)).comments) == 5


@live
async def test_pages_through_comments_up_to_the_cap(scrape):
    # The reel has 1000+ comments and the page embeds only the first ~15, so 40 needs scrolling.
    reel = await scrape(LIVE_REEL, 40)
    assert len({(c.author, c.text) for c in reel.comments}) == len(reel.comments) == 40
