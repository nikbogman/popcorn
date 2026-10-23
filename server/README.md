# server

Python 3.13, managed with [uv](https://docs.astral.sh/uv/).

```sh
cp .env.example .env    # DATABASE_URL, TMDB_API_KEY, GEMINI_API_KEY (free at aistudio.google.com/apikey)
uv run python -m app.password   # sets LOGIN_PASSWORD in .env (or the path given) to a random one, mode 600
uv sync
uv run playwright install chromium
uv run --env-file .env python -m app               # http://localhost:3000 (or PORT); migrations run on start
uv run --env-file .env python -m app.reels.login   # log in to Instagram in a browser; saves the session the reel scraper uses
TEST_DATABASE_URL=postgres://… uv run pytest           # each run migrates a throwaway schema there and drops it
```

- Schema changes: add the next `app/migrations/NNNN_*.sql`. Each runs once, in name order, recorded in `schema_migration`.
- Route or shape changes: run `uv run python -m app.openapi`, then `pnpm api` in `mobile/`. A test fails while `openapi.json` is stale.
- Lint and format: `uv run ruff format && uv run ruff check`.

## Deploy (homelab)

The server runs on the homelab as the [`stacks/popcorn`](https://github.com/nikbogman/cloudberry/tree/main/stacks/popcorn) stack in [nikbogman/cloudberry](https://github.com/nikbogman/cloudberry). Setup, secrets and the deploy command are in [`stacks/README.md#popcorn`](https://github.com/nikbogman/cloudberry/blob/main/stacks/README.md#popcorn).

- Compose builds the [Dockerfile](Dockerfile) (Python plus Playwright's Chromium, about 150 MB) on blackberry from this repo's `main`, so redeploying with `--build` picks up new commits.
- The phone reaches it at `https://raspberry.<tailnet>.ts.net/popcorn`. Tailscale strips the `/popcorn` prefix, so the server serves at `/`.
- The gateway wakes blackberry and waits for port 3000 (or `PORT`). The server only listens after migrations have run. `GET /healthz` answers without a token.
- Secrets live in the stack's `.env`: `uv run python -m app.password <cloudberry>/stacks/popcorn/.env` sets `LOGIN_PASSWORD`.
- If Postgres isn't up yet, the server exits and Docker restarts it.

## Auth

`POST /api/auth/login { password }` checks `LOGIN_PASSWORD` and returns `{ token }`. Every other route needs `Authorization: Bearer <token>`. A token lasts 90 days from its last use; `POST /api/auth/logout` ends it. Only token hashes are stored (`auth_token`). Changing `LOGIN_PASSWORD` doesn't end existing tokens; `truncate auth_token` does.

## Reel scraper (`app/reels`)

Finds which movie or TV show an Instagram reel is about. Prototype from [#14](https://github.com/nikbogman/watchlist/issues/14).

`POST /api/reels { url }` queues a job in the `reel_scrape` table; poll `GET /api/reels/{id}` until `status` is `done` (with `reel`) or `failed` (with `error`). One worker in the server process runs jobs one at a time, oldest first. `GET /api/reels` lists every job newest first, with `title` instead of the whole reel; the app shows them as Requests. A job's URL is stored as `/p/<shortcode>/`, so sharing a reel again returns its existing job (re-queued if it failed). `POST /api/reels/{id}/retry` re-queues a failed job.

**How a job runs**

1. Opens `instagram.com/p/<shortcode>/` in a shared headless Chromium, in a fresh context holding the saved session (`instagram_session` table, written by `app.reels.login`).
2. Reads the caption and comments from the JSON Instagram embeds in the page (~14 comments) and from the GraphQL responses it fetches as the comments panel is scrolled (~15 per page). Replies are skipped.
3. Asks Gemini (`gemini-3.1-flash-lite`, free AI Studio key) for the title from the caption alone, then from the caption plus each new batch of 20 comments. Stops scrolling at the first answer that names one, at 200 comments, at the last page, or after 10s with no new comments.
4. Matches a movie to TMDB by name and year (`reel.title.tmdbId`). TV shows stay unmatched.

**Gotchas**

- A bare `/reel/<code>/` link opens the viewer, which hides comments, so the scraper always uses `/p/<code>/`.
- Only real mouse-wheel events load more comments; setting `scrollTop` doesn't.
- Instagram's markup is obfuscated. The only selectors used are "the scrollable box" and the `og:description` meta tag.
- The live scrape tests in `tests/test_reels.py` run only with `INSTAGRAM_SESSION_FILE` set to an exported Playwright storage state.

**Performance** (2026-10-04, Node version, Windows laptop, a reel with ~750 top-level comments)

| Comments | Time   |
| -------- | ------ |
| ≤ 14     | 5–6s   |
| 50       | 6–7s   |
| 200      | 12–15s |
| all 749  | 33s    |

- Startup (page load, network idle) is 5–6s; scrolling then adds 15–20 comments/s.
- The worst case is 200 comments and 10 Gemini calls, within the free tier's ~15 requests/min.
- Each browser context costs memory; one browser per reel used 200–300 MB each.
- The shared Chromium closes after `BROWSER_IDLE_MINUTES` (default 5) without a job and relaunches on the next one.

**Account and session**

- The first login from a new browser hit Instagram's email-code checkpoint once; the saved session has been reused since.
- Keep concurrency at 2–3 at most; parallel sessions look most like a bot.
- When the session expires, jobs fail with a hint to run `app.reels.login`. To reuse an exported Playwright session instead, pass its path: `python -m app.reels.login path/to/state.json`.

**Known issues**

- Runs sometimes stop a few comments under the cap. The cause is unknown.
- Comments come in Instagram's "For you" order.
- If the comments panel isn't found, only the ~14 embedded comments are read.
