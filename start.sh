#!/bin/sh
set -e

# Run the Celery worker in the background so it shares the same
# filesystem (temp/<job_id>) with the bot process below.
celery -A ytvg.celery_app.celery_app worker \
    --loglevel=INFO \
    -Q text,audio,images,video,maintenance \
    --concurrency=2 &

# Run the Telegram bot (and Render's dummy health-check server) in the
# foreground. If this exits, the container stops.
exec python -m ytvg.main
