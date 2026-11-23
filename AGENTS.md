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
- `docker build -t mp3-uploader .` — build the production image.
- Configuration comes from `.env` (template: `.env.template`); `ffmpeg` must be on `PATH`.

## Architecture

- `src/config.py` — settings from env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_PERMITTED_IDS` (comma-separated Telegram user ids allowed to use the bot), `STORAGE_DIR` (where MP3s are written), `MP3_STORAGE_URL` (public base URL of that directory, with trailing slash).
- `src/utils.py` — shared download/convert helpers around `yt-dlp` and `ffmpeg`; writes ID3v2.3 tags and an embedded cover with `mutagen` (no separate image file; Telegram reads the cover from the MP3). Stored MP3s carry only per-track tags; playlist tags (album, track number) go into a temporary copy sent to Telegram, because stored files are shared across requests.
- `src/telegram/` — aiogram bot: `main.py` (polling entry point), `middleware/access_permission.py` (allow-list), `handlers/` (`text` — links, `audio` — uploaded files, `buttons` — single video vs playlist callbacks), `common.py` (download and reply).
- `src/api/` — FastAPI app under `/api/v1`: `youtube` (POST a link → MP3 URL), `mp3` (POST a file → MP3 URL). No authentication.
- Files are named by YouTube video id or Telegram file id and served from `STORAGE_DIR` as static files by nginx.

## Deployment

- `Dockerfile` — one image (`python:3.14-slim` + ffmpeg + `uv sync --frozen --no-dev`) for both processes, runs as uid 10001; default command is the bot.
- `deploy/compose.yaml` — production stack `mp3-uploader`: image `ghcr.io/antonkuzmn1/mp3-uploader:${IMAGE_TAG}`; `telegram` (bot), `api` (under the `api` profile, disabled until it gets authentication; would be routed to `mp3-uploader.xqwke.com`), `storage` (nginx, autoindex off, inline config, routed to `mp3-storage.xqwke.com`). Public services join the external Docker network `proxy` of the Traefik gateway and are routed by `Host(...)` labels.
- Server directory `/srv/apps/mp3-uploader`: `compose.yaml` and `.env` (`IMAGE_TAG`) are rewritten on every deploy; `app.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_PERMITTED_IDS`) and `storage/` (owned by uid 10001) are created by the separate infra repo and never touched by deploys. Non-secret settings live in the compose file.
- Two ways to deploy the same files: the infra playbook (bootstrap or reset: downloads `deploy/compose.yaml` from `main`, uses `IMAGE_TAG=latest`) and CI (every push to `main`).
- `.github/workflows/ci.yml` — on PRs and pushes: `uv sync`, byte-compile, import both entry points, validate the compose file. On pushes to `main` it builds the image and pushes it to GHCR tagged with the full commit SHA and `latest`, then SSHes to the server as the `deploy` user: the forced command (`deploy-app mp3-uploader`, from the infra repo) takes the image tag as the command and `deploy/compose.yaml` on stdin. Secrets (environment `production`): `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS` (`ssh-keyscan -p <port> <host>`).
