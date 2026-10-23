# Popcorn

Two apps, each with its own tooling: `mobile/` (Expo + pnpm, see [mobile/AGENTS.md](mobile/AGENTS.md)) and `server/` (Python: FastAPI + asyncpg + Postgres, plus a Playwright Instagram reel scraper run from a Postgres job queue; see [server/README.md](server/README.md)).

- Domain terms: [CONTEXT.md](CONTEXT.md). Specs: GitHub issues, one per feature (Movie lists is #1).
- Commit messages follow [COMMITS.md](COMMITS.md).
- Before committing, format and lint what you touched: `pnpm format && pnpm lint` in `mobile/` (oxfmt, oxlint), `uv run ruff format && uv run ruff check && uv run ty check` in `server/`.
- Mobile's API types are generated: after changing a route or its shapes, run `uv run python -m app.openapi` in `server/`, then `pnpm api` in `mobile/`.
- Use agent-device only for app/device automation tasks. For a normal app-driving task, start immediately.
- Run `agent-device` through mobile's install (`pnpm exec agent-device` in `mobile/`), not a global one.
