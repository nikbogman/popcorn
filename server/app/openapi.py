"""Writes openapi.json, which mobile generates its API types from. A test fails while it is stale."""

import json
from pathlib import Path

from .routes import create_app

FILE = Path(__file__).parent.parent / 'openapi.json'


def spec():
    # The spec only reads the routes, so the app needs no database or TMDB.
    return json.dumps(create_app(None, None, '').openapi(), indent=2) + '\n'  # type: ignore


if __name__ == '__main__':
    FILE.write_text(spec())
    print(f'Wrote {FILE}')
