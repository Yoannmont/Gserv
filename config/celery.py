import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_CONFIGURATION", "Dev")

import configurations

configurations.setup()

app = Celery("game_server_manager")


app.config_from_object("config:settings", namespace="CELERY")

app.autodiscover_tasks()

# Periodic tasks configuration
app.conf.beat_schedule = {
    "collect-server-metrics": {
        "task": "docker_manager.tasks.collect_server_metrics",
        "schedule": 30.0,
    },
    "sync-container-status": {
        "task": "docker_manager.tasks.sync_container_status",
        "schedule": 30.0,
    },
    "check-auto-update-servers": {
        "task": "docker_manager.tasks.check_auto_update_servers",
        "schedule": crontab(hour=4, minute=0),
    },
    "cleanup-old-metrics": {
        "task": "docker_manager.tasks.cleanup_old_metrics",
        "schedule": crontab(hour=3, minute=0),
    },
    "cleanup-old-status-history": {
        "task": "docker_manager.tasks.cleanup_old_status_history",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
