"""Celery application and tasks.

Queues: `gpu` runs ingest + transcription (Whisper benefits from a GPU), and
`cpu` runs highlight selection, reframing, FFmpeg rendering, and housekeeping.
Start one worker for both queues locally:

    celery -A snipzo.api.worker worker -Q gpu,cpu --loglevel=INFO
"""

from __future__ import annotations

from celery import Celery, chain

from snipzo.api import jobs
from snipzo.api.settings import ApiSettings, get_api_settings

celery_app = Celery("snipzo")


def configure_celery(settings: ApiSettings | None = None) -> Celery:
    """Apply settings to the Celery app (safe to call repeatedly)."""
    cfg = settings or get_api_settings()
    celery_app.conf.update(
        broker_url=cfg.redis_url,
        task_always_eager=cfg.celery_eager,
        task_eager_propagates=False,
        task_ignore_result=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_default_queue="cpu",
        task_routes={
            "snipzo.ingest_transcribe": {"queue": "gpu"},
            "snipzo.highlights_render": {"queue": "cpu"},
            "snipzo.cleanup_sources": {"queue": "cpu"},
            "snipzo.rerender_clip": {"queue": "cpu"},
            "snipzo.publish_clip": {"queue": "cpu"},
        },
        beat_schedule={
            "cleanup-sources-daily": {
                "task": "snipzo.cleanup_sources",
                "schedule": 24 * 3600.0,
            }
        },
    )
    return celery_app


configure_celery()


@celery_app.task(name="snipzo.ingest_transcribe")
def ingest_transcribe_task(job_id: str) -> bool:
    return jobs.run_ingest_and_transcribe(job_id)


@celery_app.task(name="snipzo.highlights_render")
def highlights_render_task(job_id: str) -> bool:
    return jobs.run_highlights_and_render(job_id)


@celery_app.task(name="snipzo.rerender_clip")
def rerender_clip_task(job_id: str) -> bool:
    return jobs.run_rerender(job_id)


@celery_app.task(name="snipzo.publish_clip")
def publish_clip_task(job_id: str) -> bool:
    from snipzo.api.publishing import run_publish

    return run_publish(job_id)


@celery_app.task(name="snipzo.cleanup_sources")
def cleanup_sources_task() -> list[str]:
    return jobs.cleanup_sources()


def enqueue_pipeline(job_id: str) -> None:
    """Queue ingest/transcribe on the GPU queue, then render on the CPU queue."""
    configure_celery()
    chain(
        ingest_transcribe_task.si(job_id),
        highlights_render_task.si(job_id),
    ).apply_async()


def enqueue_rerender(job_id: str) -> None:
    """Queue a single-clip re-render on the CPU queue."""
    configure_celery()
    rerender_clip_task.delay(job_id)


def enqueue_publish(job_id: str) -> None:
    """Queue a YouTube upload."""
    configure_celery()
    publish_clip_task.delay(job_id)
