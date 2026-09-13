from celery import Celery
from celery.schedules import crontab

from app.config import get_settings, validate_prod_secrets

settings = get_settings()
validate_prod_secrets(settings)

celery_app = Celery(
    "hydenlyne_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.document_tasks"],
)

QUEUE_DEFAULT = "default"
QUEUE_HIGH_PRIORITY = "high_priority"
QUEUE_HEAVY_COMPUTE = "heavy_compute"
QUEUE_INDEXING = "indexing"

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        "app.tasks.document_tasks.process_document_extraction": {"queue": QUEUE_HEAVY_COMPUTE},
        "app.tasks.document_tasks.process_dropbox_document": {"queue": QUEUE_HEAVY_COMPUTE},
        "app.tasks.document_tasks.check_expiring_certifications": {"queue": QUEUE_HIGH_PRIORITY},
        "app.tasks.document_tasks.index_document_embeddings": {"queue": QUEUE_INDEXING},
    },
    task_default_queue=QUEUE_DEFAULT,
    task_queue_max_priority=10,
    task_default_priority=5,
    beat_schedule={
        "check-expiring-certifications": {
            "task": "app.tasks.document_tasks.check_expiring_certifications",
            "schedule": crontab(hour=0, minute=0),
        },
    },
)
