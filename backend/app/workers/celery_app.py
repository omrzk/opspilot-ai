"""Celery application. Broker and result backend are both Redis."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "opspilot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=60 * 20,
    task_soft_time_limit=60 * 18,
    broker_connection_retry_on_startup=True,
    result_expires=60 * 60 * 24,
)
