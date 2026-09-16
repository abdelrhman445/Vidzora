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

## Temp files

`TempWorkspaceManager` isolates every job under `TEMP_DIR/<job_id>/`. `cleanup_job` runs after success, cancel, and (via Celery beat) for workspaces older than `TEMP_TTL_HOURS`. Path traversal in `job_id` is rejected.
