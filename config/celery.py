import os

from celery import Celery
from celery.schedules import crontab

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_CONFIGURATION", "Dev")

import configurations

configurations.setup()

app = Celery("game_server_manager")

# Configuration from Django settings
app.config_from_object("config:settings", namespace="CELERY")

# Auto-discover tasks in Django apps
app.autodiscover_tasks()

# Periodic tasks configuration
app.conf.beat_schedule = {
    # Collect metrics every 30 seconds
    "collect-server-metrics": {
        "task": "docker_manager.tasks.collect_server_metrics",
        "schedule": 300.0,  # Every 30 seconds
    },
    # Synchronize statuses every minute
    "sync-container-status": {
        "task": "docker_manager.tasks.sync_container_status",
        "schedule": 20.0,
    },
    # Check automatic updates at 4 AM
    "check-auto-update-servers": {
        "task": "docker_manager.tasks.check_auto_update_servers",
        "schedule": crontab(hour=4, minute=0),
    },
    # Clean up old metrics daily at 3 AM
    "cleanup-old-metrics": {
        "task": "docker_manager.tasks.cleanup_old_metrics",
        "schedule": crontab(hour=3, minute=0),
    },
    # Clean up history every Monday at 2 AM
    "cleanup-old-status-history": {
        "task": "docker_manager.tasks.cleanup_old_status_history",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
