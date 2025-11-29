import os

from celery import Celery
from celery.schedules import crontab

# Définit le module de settings Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_CONFIGURATION", "Dev")

import configurations

configurations.setup()

app = Celery("game_server_manager")

# Configuration depuis Django settings
app.config_from_object("config:settings", namespace="CELERY")

# Découverte automatique des tâches dans les apps Django
app.autodiscover_tasks()

# Configuration des tâches périodiques
app.conf.beat_schedule = {
    # Collecte des métriques toutes les 30 secondes
    "collect-server-metrics": {
        "task": "docker_manager.tasks.collect_server_metrics",
        "schedule": 300.0,  # Toutes les 30 secondes
    },
    # Synchronisation des statuts toutes les minutes
    "sync-container-status": {
        "task": "docker_manager.tasks.sync_container_status",
        "schedule": 20.0,
    },
    # Vérification des mises à jour automatiques à 4h du matin
    "check-auto-update-servers": {
        "task": "docker_manager.tasks.check_auto_update_servers",
        "schedule": crontab(hour=4, minute=0),
    },
    # Nettoyage des anciennes métriques tous les jours à 3h
    "cleanup-old-metrics": {
        "task": "docker_manager.tasks.cleanup_old_metrics",
        "schedule": crontab(hour=3, minute=0),
    },
    # Nettoyage de l'historique tous les lundis à 2h
    "cleanup-old-status-history": {
        "task": "docker_manager.tasks.cleanup_old_status_history",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
