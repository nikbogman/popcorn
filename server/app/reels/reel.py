from typing import Literal

from ..api import Api


class Comment(Api):
    """created_at is an ISO date string, so a reel reads back from the jsonb column unchanged."""

    author: str
    text: str
    likes: int
    created_at: str


class Title(Api):
    """What the reel shows. tmdb_id is None for TV shows and for movies TMDB doesn't know."""

    name: str
    year: int | None
    kind: Literal['movie', 'tv']
    tmdb_id: int | None


class Reel(Api):
    """title: None = the reel doesn't say what it shows, or it hasn't been identified yet."""

    url: str
    description: str | None
    comments: list[Comment]
    title: Title | None = None
