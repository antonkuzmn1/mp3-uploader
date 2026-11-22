# mp3-uploader

Telegram bot and HTTP API that download audio (YouTube via `yt-dlp`, or files sent to the bot), convert it to MP3 with `ffmpeg` and publish it as a static file. Stack: Python 3.14, aiogram 3, FastAPI, uv.

## Rules

- Make git commits yourself after completing changes. Never push.
- Commit messages: English, Conventional Commits format (`feat: ...`, `fix: ...`, `chore: ...`, `docs: ...`, etc.).
- Everything in code must be in English: identifiers, comments, commit messages, docs in the repo.
- Never commit secrets (`.env`, tokens) or context tied to the local machine/environment (absolute paths, local tooling, personal settings). Put it in local docs (see below).
- Commit only docs that are independent of the local machine/environment.

## Agent docs

- `AGENTS.md` (this file) is the single source of truth for any coding agent (Codex, Claude Code, Gemini CLI, ...).
- `CLAUDE.md` and `GEMINI.md` are thin shims that only import this file (and the local file below); never put content there.

## Local docs (not committed)

- `AGENTS.local.md` in the repo root — machine-specific notes: local paths, installed tools, ports, env quirks, personal preferences. Agents should read it if it exists.
- `*.local.md` anywhere — additional local notes next to the code they relate to.
- Both patterns are gitignored. Committed docs must stand on their own and never require a local doc.

## Commands

- `uv sync` — install dependencies into `.venv`.
- `uv run python -m src.telegram.main` — run the bot.
- `uv run uvicorn src.api.main:app --reload` — run the API on port 8000.
- Configuration comes from `.env` (template: `.env.template`); `ffmpeg` must be on `PATH`.

## Architecture

- `src/config.py` — settings from env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_PERMITTED_IDS` (comma-separated Telegram user ids allowed to use the bot), `STORAGE_DIR` (where MP3s are written), `MP3_STORAGE_URL` (public base URL of that directory, with trailing slash).
- `src/utils.py` — shared download/convert helpers around `yt-dlp` and `ffmpeg`.
- `src/telegram/` — aiogram bot: `main.py` (polling entry point), `middleware/access_permission.py` (allow-list), `handlers/` (`text` — links, `audio` — uploaded files, `buttons` — single video vs playlist callbacks), `common.py` (download and reply).
- `src/api/` — FastAPI app under `/api/v1`: `youtube` (POST a link → MP3 URL + thumbnail), `mp3` (POST a file → MP3 URL). No authentication.
- Files are named by YouTube video id or Telegram file id and served from `STORAGE_DIR` by a separate nginx container (`nginx.conf`, autoindex on).

## Deployment (current, legacy)

- `docker/base/Dockerfile` — Python + ffmpeg + dependencies; `docker/api` and `docker/telegram` build on top of it (`FROM <registry>/mp3-uploader/base:latest`).
- `docker-compose.yml` — `telegram`, `api`, `nginx` sharing `./storage`, on the external network `xqwke`, images from a private registry.
- `.github/workflows/deploy.yml` — self-hosted runner builds and pushes all images, copies the compose file to `vars.PATH` and restarts it.
