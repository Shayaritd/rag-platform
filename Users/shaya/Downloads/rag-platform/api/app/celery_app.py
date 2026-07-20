from celery import Celery
from app.core.config import get_settings

import importlib.util

settings = get_settings()

include_tasks = []
if importlib.util.find_spec("worker"):
    include_tasks.append("worker.tasks.ingestion")

celery_app = Celery("rag_platform", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND,
                     include=include_tasks)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,          # redeliver if a worker dies mid-task
    worker_prefetch_multiplier=1, # avoid one worker hoarding jobs under uneven doc sizes
    task_default_retry_delay=10,
)
