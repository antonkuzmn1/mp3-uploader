# One image for both processes: the bot and the API differ only in the command (see deploy/compose.yaml).
FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so they stay cached until the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/

# Unprivileged runtime user; the storage directory on the host must be owned by this uid.
RUN useradd --uid 10001 --user-group --no-create-home --home-dir /app app \
    && install -d -o app -g app /app/storage
USER 10001

ENV STORAGE_DIR=/app/storage

CMD ["python", "-m", "src.telegram.main"]
