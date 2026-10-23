# The server, with the Chromium the reel scraper drives.
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

# Dependencies first, so code changes don't redo the install or the ~150 MB browser download.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
# Chromium matching the installed Playwright, plus the system libraries it needs.
RUN playwright install --with-deps chromium

COPY watcher watcher
CMD ["python", "-m", "watcher"]
