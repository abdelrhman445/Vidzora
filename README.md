# YouTube Automation Bot

Semi-automated YouTube Shorts/video generator controlled entirely through a
Telegram bot, with a mandatory **human approval gateway** before every
resource-intensive step (audio synthesis, visual generation, final render).

## Architecture

```
Telegram user
   │  (topic OR full script)
   ▼
aiogram bot (async, FSM) ───────► MongoDB (VideoJob: single source of truth)
   │  .delay()                         ▲
   ▼                                   │ read/write status
Celery task (sync worker process) ─────┘
   │
   ├─ Gemini API           → structured JSON script (AI mode)
   │                          OR scene-segmentation only (custom-script mode)
   ├─ edge-tts              → per-scene voiceover mp3
   ├─ HuggingFace/Leonardo  → AI image (per scene, if visual_type=image)
   ├─ Pexels API            → stock video clip (per scene, if visual_type=video)
   └─ MoviePy/ffmpeg        → crossfades + captions + music + intro/outro → final .mp4
   │
   ▼
notify.py sends the result + inline [Continue/Regenerate/Cancel] keyboard
back to the same Telegram chat, independently of the bot's polling loop.
```

The bot process and the Celery worker process are **decoupled** — the bot
never blocks on generation, and the worker never blocks on Telegram I/O
beyond the notification call itself.

## Two ways to start a video

`/new_video` first asks which mode you want:

- **🤖 AI writes it** — send a topic, Gemini writes a full script. Goes
  through the **Script approval gate** before anything else runs.
- **📝 I have my own script** — paste your full script as one message.
  Gemini only *segments* it into scenes and writes an image prompt per
  scene — it is instructed to copy your wording verbatim, never rewrite
  it. This mode **skips the Script approval gate** entirely (you already
  approved it by writing it) and goes straight into voiceover generation.

Either way, the Audio → Visuals → Render gates still apply.

## Mixed visuals: AI images + real stock clips

Set `ENABLE_STOCK_FOOTAGE=true` and add a free `PEXELS_API_KEY` and Gemini
will tag each scene `visual_type: image` or `visual_type: video` based on
whether it's a static/conceptual beat or a motion/real-world one. The
Visuals stage then either generates an AI still or pulls a matching Pexels
clip per scene — **both can appear in the same final video**. If no stock
clip matches, that scene silently falls back to an AI image so the
pipeline never stalls.

## Professional final render

The render stage (`src/services/render_service.py`) now does more than
concatenate clips:

- **Crossfade transitions** between every scene (`CROSSFADE_DURATION_SEC`).
- **Burned-in captions** synced to each scene's voiceover
  (`ENABLE_SUBTITLES`, `SUBTITLE_FONT_SIZE`, `SUBTITLE_FONT_PATH`).
- **Background music**, mixed low under the voiceover — opt-in, you supply
  your own royalty-free track (`assets/music/`, `BACKGROUND_MUSIC_PATH`,
  `BACKGROUND_MUSIC_VOLUME`). No music ships with the repo.
- **Intro/outro title cards** (`ENABLE_INTRO_CARD`, `ENABLE_OUTRO_CARD`,
  `OUTRO_TEXT`).
- Stock video clips are center-cropped/looped to exactly match each
  scene's voiceover duration; AI images get a subtle Ken Burns zoom.

## Pipeline & Approval Gateways

1. `/new_video` → choose AI script or paste your own.
2. **Script** (AI mode only) → sent to chat → `[Continue|Regenerate|Cancel]`
3. **Audio** (edge-tts, per scene) → sent to chat → `[Continue|Regenerate|Cancel]`
4. **Visuals** (AI images and/or stock clips, per scene) → sent to chat → `[Continue|Regenerate|Cancel]`
5. **Render** (MoviePy/ffmpeg — transitions, captions, music, intro/outro) →
   final `.mp4` sent to chat → temp workspace wiped.

Every stage writes its status onto the `VideoJob` document in MongoDB, so
the pipeline state survives bot restarts.

## Running locally

```bash
cp .env.example .env   # fill in BOT_TOKEN, GEMINI_API_KEY, HUGGINGFACE_API_KEY, etc.
docker compose up --build
```

This starts Redis, MongoDB, the bot, a Celery worker, and Celery beat
(hourly sweep of any orphaned temp folders from crashed jobs).

## Running without Docker

```bash
pip install -r requirements.txt
# terminal 1
python -m src.main
# terminal 2
celery -A src.celery_app.celery worker --loglevel=info -Q video_pipeline
# terminal 3 (optional)
celery -A src.celery_app.celery beat --loglevel=info
```

Requires `ffmpeg` on PATH, and local/running Redis + MongoDB instances.

## Temp file management

Every job gets an isolated folder: `temp/{video_id}/{scripts,audio,images,output}/`.
`JobWorkspace.cleanup()` (`src/utils/file_manager.py`) removes it on
success, cancellation, or failure — called explicitly in `render_tasks.py`'s
`finally` block and in the `/cancel` and Cancel-button handlers. A Celery
beat job also purges any folder older than 24h as a safety net against
crashed workers.

## Why not deploy this on Vercel?

Vercel's serverless functions are stateless, short-lived, and have no
persistent filesystem or long-running worker concept — ffmpeg rendering
and a Celery worker that stays alive processing a queue don't fit that
model. Use a VPS (the `docker-compose.yml` here is ready to go),
Railway, Render, or Fly.io instead — anything that runs Docker with
persistent volumes and long-running processes.

## Deploying on Heroku

Heroku works here (unlike Vercel) because dynos are persistent processes,
not short-lived serverless functions — that's exactly what the bot's
long-polling loop and the Celery worker need.

**Recommended: container deploy** (reuses the existing `Dockerfile`, which
already installs `ffmpeg` — no extra buildpack needed):

```bash
heroku create your-app-name
heroku stack:set container -a your-app-name
heroku addons:create heroku-redis:mini -a your-app-name   # or use REDIS_URL from Redis Cloud
# Heroku has no MongoDB add-on — use MongoDB Atlas (free tier) and set MONGO_URI accordingly
heroku config:set BOT_TOKEN=... GEMINI_API_KEY=... MONGO_URI=... -a your-app-name
git push heroku main
heroku ps:scale bot=1 worker=1 beat=1 -a your-app-name
```

`heroku.yml` defines three process types (`bot`, `worker`, `beat`) built
from the same Dockerfile. None of them is a `web` dyno — the bot doesn't
serve HTTP, it long-polls Telegram, so it isn't subject to Heroku's 30s
web-request timeout at all.

**Alternative: buildpack deploy** (no Docker) — a `Procfile` and
`runtime.txt` are included too, but you'd need to add the
`heroku-buildpack-ffmpeg-latest` buildpack manually since the Python
buildpack doesn't install ffmpeg.

**Caveats specific to Heroku:**
- Dynos restart roughly every 24h; if that happens mid-render, the task
  is safe (Celery's `task_acks_late=True` requeues unacknowledged tasks)
  but the user will see a delayed rather than instant result.
- The dyno filesystem is ephemeral between restarts — fine here, since
  every job's temp folder is created and wiped within a single task run,
  never relied on across restarts.
- Basic/Standard-1X dynos have 512MB–1GB RAM; long or high-res renders
  can get memory-heavy with MoviePy — Standard-2X (2.5GB) is safer for
  regular use.

## Extending

- Swap `IMAGE_PROVIDER=leonardo` in `.env` to use Leonardo AI instead of
  Hugging Face — no code changes needed, see `src/services/image_service.py`.
- Add new pipeline stages by adding a `PipelineStage`, a Celery task, and a
  branch in `src/bot/handlers/approval.py`'s dispatch table.
