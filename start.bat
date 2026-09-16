@echo off
echo Starting Celery Worker...
start cmd /k "set PYTHONPATH=src && celery -A ytvg.celery_app.celery_app worker -l INFO -P solo -Q text,audio,images,video,maintenance"

echo Starting Telegram Bot...
set PYTHONPATH=src
python -m ytvg.main