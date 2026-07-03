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
    # Fail fast when publishing if the broker is briefly unreachable, so callers that
    # enqueue best-effort work (e.g. demo seeding) fall back quickly instead of hanging.
    broker_transport_options={"max_retries": 1},
    task_publish_retry_policy={"max_retries": 1, "interval_start": 0, "interval_step": 0.2},
)

# In demo mode, sweep expired sessions every few minutes via Celery beat.
if settings.demo_mode:
    celery_app.conf.beat_schedule = {
        "purge-demo-sessions": {
            "task": "opspilot.purge_demo_sessions",
            "schedule": 300.0,
        }
    }
