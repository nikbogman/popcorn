from watcher.openapi import FILE, spec


def test_openapi_json_matches_the_routes():
    assert FILE.read_text() == spec(), 'run `uv run python -m watcher.openapi`, then `pnpm api` in mobile/'
