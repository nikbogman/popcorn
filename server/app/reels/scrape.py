import asyncio
import contextlib
import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from playwright.async_api import BrowserContext, Response

from ..api import iso
from .reel import Comment, Reel

LOGIN_HINT = 'run `uv run python -m app.reels.login` in server/'

REEL_URL = re.compile(r'^https://(www\.)?instagram\.com/([\w.]+/)?(reels?|p)/(?P<shortcode>[\w-]+)')

# Called with the reel so far after every page of comments, and once more with final = True. Returning True stops scraping.
Until = Callable[[Reel, bool], Awaitable[bool]]

# The one scrollable box inside the page: the comments panel.
PANEL_CENTER = """() => {
  const el = [...document.querySelectorAll('body *')].find(
    (e) => e.scrollHeight > e.clientHeight + 5 && /auto|scroll/.test(getComputedStyle(e).overflowY),
  )
  const r = el?.getBoundingClientRect()
  return r && { x: r.x + r.width / 2, y: r.y + r.height / 2 }
}"""


def shortcode_of(url: str):
    """The reel's shortcode, or None when the URL isn't an Instagram reel or post."""
    m = REEL_URL.match(url)
    return m['shortcode'] if m else None


async def _never(reel: Reel, final: bool):
    return False


async def scrape_reel(context: BrowserContext, url: str, max_comments=200, until: Until | None = None) -> Reel:
    """Scrapes in a new page of the given context, which must hold a logged-in Instagram session."""
    until = until or _never
    shortcode = shortcode_of(url)
    if not shortcode:
        raise ValueError(f'{url} is not an Instagram reel or post URL')

    page = await context.new_page()
    try:
        comments: dict[str, Comment] = {}
        # Once seen in a payload, None means the reel has no caption.
        caption_seen = False
        description: str | None = None
        has_next_page = True

        # Instagram embeds the first page in the HTML document and fetches later pages as GraphQL JSON.
        async def collect(res: Response):
            nonlocal caption_seen, description, has_next_page
            if not re.search(r'instagram\.com/(graphql|api|p/|reels?/)', res.url):
                return
            try:
                body = await res.text()
            except Exception:
                return
            for payload in _json_payloads(body):
                for node in _walk(payload):
                    if node.get('code') == shortcode and 'caption' in node and not caption_seen:
                        caption_seen = True
                        description = (node['caption'] or {}).get('text')
                    connection = node.get('xdt_api__v1__media__media_id__comments__connection')
                    if not connection:
                        continue
                    has_next_page = (connection.get('page_info') or {}).get('has_next_page', has_next_page)
                    for edge in connection.get('edges') or []:
                        c = edge['node']
                        if c.get('parent_comment_id'):
                            continue
                        comments[c['pk']] = Comment(
                            author=c['user']['username'],
                            text=c['text'],
                            likes=c.get('comment_like_count') or 0,
                            created_at=iso(datetime.fromtimestamp(c['created_at'], UTC)),
                        )

        pending: list[asyncio.Task] = []
        page.on('response', lambda res: pending.append(asyncio.create_task(collect(res))))

        async def settle():
            # Waits for every response seen so far, including ones that arrive while waiting.
            while pending:
                batch = pending[:]
                pending.clear()
                await asyncio.gather(*batch)

        async def reel_so_far():
            if caption_seen:
                caption = description
            else:
                try:
                    caption = await page.locator('meta[property="og:description"]').get_attribute('content', timeout=1000)
                except Exception:
                    caption = None
            return Reel(url=url, description=caption, comments=list(comments.values())[:max_comments])

        # A bare /reel/ link opens the full-screen viewer, which hides comments; /p/ opens the post view with them.
        await page.goto(f'https://www.instagram.com/p/{shortcode}/', wait_until='networkidle')
        if '/accounts/login' in page.url:
            raise RuntimeError(f'Instagram session expired, {LOGIN_HINT}')
        await settle()
        stopped = await until(await reel_so_far(), False)

        # Wheel over the comments panel until the cap or the last page.
        # Setting scrollTop doesn't trigger Instagram's pagination; real wheel events do.
        center = await page.evaluate(PANEL_CENTER)
        if center:
            await page.mouse.move(center['x'], center['y'])
        # Stops after 10s with no new comments in case Instagram stalls without saying it's on the last page.
        idle = 0
        while not stopped and center and has_next_page and len(comments) < max_comments and idle < 20:
            before = len(comments)
            await page.mouse.wheel(0, 2000)
            await page.wait_for_timeout(500)
            await settle()
            idle = 0 if len(comments) > before else idle + 1
            if len(comments) > before:
                stopped = await until(await reel_so_far(), False)

        reel = await reel_so_far()
        if not stopped:
            await until(reel, True)
        return reel
    finally:
        await page.close()


def _json_payloads(body: str):
    """JSON bodies are parsed whole; HTML documents yield their embedded `application/json` scripts."""
    if body.lstrip().startswith('<'):
        sources = re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', body, re.S)
    else:
        sources = body.split('\n')  # GraphQL can stream several JSON objects, one per line
    for s in sources:
        with contextlib.suppress(ValueError):
            yield json.loads(s)


def _walk(value):
    """Every dict nested anywhere in value, value included."""
    if isinstance(value, dict):
        yield value
        children = value.values()
    elif isinstance(value, list):
        children = value
    else:
        return
    for child in children:
        yield from _walk(child)
