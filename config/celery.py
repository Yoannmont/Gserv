import os

from celery import Celery, signals
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_CONFIGURATION", "Dev")

from configurations import importer
from request_id import get_current_request_id, local

importer.install()
app = Celery("game_server_manager")


app.config_from_object("config.settings", namespace="CELERY")

app.autodiscover_tasks()

# Periodic tasks configuration
app.conf.beat_schedule = {
    "collect-server-metrics": {
        "task": "docker_manager.tasks.collect_server_metrics",
        "schedule": 300.0,
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
    "delete-unused-containers": {
        "task": "docker_manager.tasks.delete_unused_containers",
        "schedule": crontab(hour=1, minute=0),
    },
    "auto-backup-servers": {
        "task": "docker_manager.tasks.auto_backup_servers",
        "schedule": crontab(hour=3, minute=30),
    },
    "cleanup-old-backups": {
        "task": "docker_manager.tasks.cleanup_old_backups",
        "schedule": crontab(hour=4, minute=30),
    },
}


# Add request_id to the headers of the task
@signals.before_task_publish.connect
def add_request_id(headers=None, **kwargs):
    request_id = get_current_request_id()
    if request_id:
        headers["request_id"] = request_id


# Add request_id to the logger
@signals.task_prerun.connect
def load_request_id(task=None, **kwargs):
    request_id = task.request.headers.get("request_id") if task.request.headers else None
    if request_id:
        local.request_id = request_id
