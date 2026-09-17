bot: python -m src.main
worker: celery -A src.celery_app.celery worker --loglevel=info -Q video_pipeline --concurrency=2
beat: celery -A src.celery_app.celery beat --loglevel=info
