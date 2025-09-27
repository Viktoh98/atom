# api/apps.py
from django.apps import AppConfig
import sys
import os
import logging

logger = logging.getLogger(__name__)

def _is_management_command():
    # When running management commands (migrate, makemigrations, test, etc.)
    # we should not start the scheduler.
    mgmt_cmds = {
        "migrate", "makemigrations", "collectstatic", "createsuperuser",
        "shell", "test", "loaddata", "flush"
    }
    # sys.argv may be like ['manage.py', 'migrate']
    if len(sys.argv) >= 2 and sys.argv[1] in mgmt_cmds:
        return True
    # also don't start when running django-admin tasks (CI etc.) or when running as uwsgi/management
    if os.getenv("SKIP_SCHEDULER", "").lower() in ("1", "true", "yes"):
        return True
    return False

class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        if _is_management_command():
            logger.info("Skipping scheduler start because management command detected.")
            return
        try:
            # start scheduler (your scheduler.start() function)
            from . import scheduler
            scheduler.start()
        except Exception as exc:
            logger.exception("Failed to start scheduler: %s", exc)
