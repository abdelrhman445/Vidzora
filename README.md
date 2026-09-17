# Semi-Automated YouTube Video Generator

Telegram-controlled pipeline with **approval gateways** at every expensive stage.

Workers never jump ahead. After script, audio, or images are produced, Celery publishes an event on Redis. The bot process is the only component that talks to Telegram: it sends the preview plus `[Continue] / [Regenerate] / [Cancel]` and waits. Celery is not started for the next stage until `PipelineService.approve` enqueues it.

## Folder structure (Clean Architecture)

```
.
├── docker-compose.yml          Redis + Mongo + bot + worker
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── .env.example
├── src/ytvg/
│   ├── main.py                 Bot process entrypoint
│   ├── celery_app.py           Celery app, queues, beat sweep
│   ├── config.py               Pydantic settings
│   ├── domain/                 Entities, enums, errors (no I/O)
│   ├── application/
│   │   ├── ports.py            Interfaces (repository, TTS, bus, …)
│   │   └── pipeline.py         Approval-gated use cases
│   ├── infrastructure/
│   │   ├── db/                 Motor + Mongo repository
│   │   ├── messaging/          Redis pub/sub + Celery dispatcher
│   │   ├── ai/                 Gemini, edge-tts, Pollinations
│   │   ├── media/              FFmpeg assembler
│   │   └── storage/            Temp workspace manager
│   ├── presentation/           aiogram routers, FSM, keyboards, listener
│   └── workers/tasks.py        Stage tasks; publish events back to the bot
├── tests/
└── temp/                       Per-job workspaces (gitignored, wiped on finish/cancel)
```

## Pipeline

1. User sends a prompt (`/start` then text, or any idle text).
2. **Script** — Gemini JSON → bot shows scenes → wait for approval.
3. **Audio** — `edge-tts` per scene + combined preview → wait.
4. **Images** — Pollinations album → wait.
5. **Video** — FFmpeg stills + narration → send MP4 → wipe `temp/<job_id>/`.

Queues: `text`, `audio`, `images`, `video`, `maintenance`.

Worker → bot communication:

```
Celery task finishes
  → Mongo status = awaiting_approval
  → Redis PUBLISH ytvg:bot:events
  → BotEventListener sends Telegram preview + inline keyboard
  → User taps Continue
  → PipelineService.approve() enqueues the next Celery task
```

## Run locally

1. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, and `POLLINATIONS_API_KEY`.
2. Install FFmpeg and Python 3.10+.
3. Start Redis and Mongo (`docker compose up redis mongo -d`).
4. `pip install -e ".[dev]"`
5. Two processes:

```bash
set PYTHONPATH=src
python -m ytvg.main
celery -A ytvg.celery_app.celery_app worker -l INFO -Q text,audio,images,video,maintenance
```

Or `docker compose up --build`.

## Deploy on Render

The bot process and the Celery worker **must run in the same container** — the
worker writes audio/image/video files to `temp/<job_id>/` and the bot reads
those same files from disk to send them on Telegram. `start.sh` runs both
processes together (worker in the background, bot in the foreground), and the
`Dockerfile` uses it as the entrypoint.

1. Provision MongoDB (e.g. MongoDB Atlas free tier) and Redis (e.g. Render Key
   Value or Upstash) and grab their connection strings.
2. On Render: **New → Blueprint**, point it at this repo (it will read
   `render.yaml`) — or **New → Web Service** with the Docker environment if
   you'd rather set it up by hand.
3. Fill in the environment variables it asks for (`TELEGRAM_BOT_TOKEN`,
   `MONGODB_URI`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`,
   `GEMINI_API_KEY`, `POLLINATIONS_API_KEY`, ...).
4. Keep the instance count at **1** — running multiple replicas would split
   jobs across containers that don't share a disk, breaking the
   worker→bot handoff described above.
5. Deploy. Render sets `PORT` automatically; `main.py`'s dummy `aiohttp`
   server binds to it so Render's health check passes while `dp.start_polling`
   handles the actual Telegram traffic.

## Temp files

`TempWorkspaceManager` isolates every job under `TEMP_DIR/<job_id>/`. `cleanup_job` runs after success, cancel, and (via Celery beat) for workspaces older than `TEMP_TTL_HOURS`. Path traversal in `job_id` is rejected.
