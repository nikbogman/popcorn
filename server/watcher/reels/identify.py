import json
from collections.abc import Awaitable, Callable

import httpx

from ..tmdb import Tmdb
from .reel import Reel, Title

# Free tier on a Google AI Studio key. A small model is enough: the caption or comments usually name the title.
MODEL = 'gemini-3.1-flash-lite'
API = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent'

ANSWER = {
    'type': 'object',
    'properties': {
        'found': {'type': 'boolean'},
        'name': {'type': 'string'},
        'year': {'type': ['integer', 'null']},
        'kind': {'type': 'string', 'enum': ['movie', 'tv']},
    },
    'required': ['found', 'name', 'year', 'kind'],
}

Identify = Callable[[Reel], Awaitable[Title | None]]


def _prompt(reel: Reel):
    return '\n'.join(
        [
            'Which movie or TV show is this Instagram reel a clip of or about? Use the caption and the comments.',
            'Answer found: false when they do not make it clear. Give the original release year when you know it.',
            '',
            f'Caption: {reel.description or "(none)"}',
            'Comments, most liked first:',
            *(f'- {c.text}' for c in sorted(reel.comments, key=lambda c: -c.likes)),
        ]
    )


class Batches:
    """
    Identifies a reel while it is scraped: first the caption alone, then each new batch of comments (with the caption)
    in turn. `until`, given to scrape_reel, stops the scrape at the first one that names the title.
    """

    def __init__(self, identify: Identify, size=20):
        self.identify = identify
        self.size = size
        self.asked_caption = False
        self.checked = 0
        self.title: Title | None = None

    async def until(self, reel: Reel, final: bool):
        # Captions often name the film outright, so this usually ends the scrape before any scrolling.
        if not self.asked_caption:
            self.asked_caption = True
            if reel.description:
                self.title = await self.identify(reel.model_copy(update={'comments': []}))
        while self.title is None:
            batch = reel.comments[self.checked : self.checked + self.size]
            if not batch or (len(batch) < self.size and not final):
                return False
            self.checked += len(batch)
            self.title = await self.identify(reel.model_copy(update={'comments': batch}))
            if len(batch) < self.size:
                break
        return self.title is not None


def create_identifier(api_key: str, tmdb: Tmdb, transport: httpx.AsyncBaseTransport | None = None) -> Identify:
    """Asks Gemini what the reel shows, then matches a movie to TMDB. None when the reel doesn't say."""
    client = httpx.AsyncClient(transport=transport, timeout=60)

    async def identify(reel: Reel):
        res = await client.post(
            API,
            headers={'x-goog-api-key': api_key},
            json={
                'contents': [{'parts': [{'text': _prompt(reel)}]}],
                'generationConfig': {'responseMimeType': 'application/json', 'responseJsonSchema': ANSWER},
            },
        )
        if res.is_error:
            raise RuntimeError(f'Gemini failed with {res.status_code}: {res.text}')
        try:
            text = res.json()['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError, ValueError):
            raise RuntimeError('Gemini returned no answer') from None
        answer = json.loads(text)
        name, year, kind = answer['name'], answer['year'], answer['kind']
        if not answer['found'] or not name:
            return None

        # ponytail: the Tmdb client only searches movies, so TV shows stay unmatched.
        if kind == 'tv':
            return Title(name=name, year=year, kind=kind, tmdb_id=None)
        # ponytail: first search result with Gemini's year (any result when it gave none); no fuzzy title match.
        match = next((m for m in await tmdb.search(name) if year is None or m.year == year), None)
        if match:
            return Title(name=match.title, year=match.year, kind=kind, tmdb_id=match.tmdb_id)
        return Title(name=name, year=year, kind=kind, tmdb_id=None)

    return identify
