"""Tests for Celery task routing and worker queue segregation."""

from app.tasks.celery_app import (
    QUEUE_DEFAULT,
    QUEUE_HEAVY_COMPUTE,
    QUEUE_HIGH_PRIORITY,
    QUEUE_INDEXING,
    celery_app,
)


def test_celery_queue_routing_configuration():
    """Verify tasks are routed to their designated queues to avoid worker starvation."""
    routes = celery_app.conf.task_routes
    assert routes is not None

    # Heavy compute tasks (PDF parsing, OCR, Ollama extraction)
    assert routes.get("app.tasks.document_tasks.process_document_extraction") == {
        "queue": QUEUE_HEAVY_COMPUTE
    }
    assert routes.get("app.tasks.document_tasks.process_dropbox_document") == {
        "queue": QUEUE_HEAVY_COMPUTE
    }

    # Indexing tasks (embeddings)
    assert routes.get("app.tasks.document_tasks.index_document_embeddings") == {
        "queue": QUEUE_INDEXING
    }

    # High priority / periodic compliance checks
    assert routes.get("app.tasks.document_tasks.check_expiring_certifications") == {
        "queue": QUEUE_HIGH_PRIORITY
    }

    # Default queue remains "default"
    assert celery_app.conf.task_default_queue == QUEUE_DEFAULT
