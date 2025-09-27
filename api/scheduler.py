import logging
import sys, os
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django.db import close_old_connections
from django.conf import settings
from .task.fetcher import fetch_and_store_reviews_for_domain
from .storage import load_json, logger as log_job
logger = logging.getLogger(__name__)
JOB_ID = "fetch_reviews_job"

def _job_wrapper():
    # ensure DB connections aren't held across runs
    close_old_connections()
    try:
        tracked = load_json("tracked.json") or []
        if isinstance(tracked, dict):
            tracked = tracked.get("tracked", []) or []

        if not tracked:
            log_job("Scheduler run: no tracked domains")
            return

        for domain in tracked:
            # fresh connection per domain
            close_old_connections()
            try:
                fetch_and_store_reviews_for_domain(domain)
            except Exception as e:
                # safe logging, don't raise
                log_job(f"Error in domain {domain}: {e}")
                logger.exception("Error processing domain %s", domain)
    except Exception as exc:
        log_job(f"Scheduler top-level error: {exc}")
        logger.exception("Scheduler top-level error")
    finally:
        close_old_connections()

_scheduler = None

def start():
    global _scheduler
    if _scheduler:
        return _scheduler

    # don't start during management commands or parent autoreloader
    mgmt = {"migrate","makemigrations","collectstatic","test","shell"}
    if len(sys.argv) >= 2 and sys.argv[1] in mgmt:
        logger.info("Not starting scheduler during management command.")
        return

    if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
        logger.info("Not starting scheduler in parent runserver process.")
        return

    # job defaults: avoid overlapping runs
    job_defaults = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 300}
    scheduler = BackgroundScheduler(timezone="UTC", job_defaults=job_defaults)

    # NB: using in-memory jobstore only (no DB writes) to avoid sqlite locking problems
    scheduler.add_job(
        _job_wrapper,
        "interval",
        minutes=5,   
        id=JOB_ID,
        replace_existing=True,
    )

    # optional cleanup job (in-memory only)
    scheduler.add_job(
        lambda: log_job("cleanup job executed"),
        "interval",
        hours=24,
        id="cleanup_old_job_executions",
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started (in-memory): fetch_reviews every 5 minutes.")
    log_job("Scheduler started (in-memory): fetch_reviews every 5 minutes.")
    return scheduler
