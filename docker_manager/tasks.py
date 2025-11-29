import logging

from celery import shared_task
from django.utils import timezone
from django.db import transaction

from servers.models import ServerStatus

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def start_server_task(self, server_id: int):
    """
    Tâche asynchrone pour démarrer un serveur

    Args:
        server_id: ID du serveur à démarrer
    """
    try:
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance, ServerStatus

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        # Change le statut
        server.status = "starting"
        server.save(update_fields=["status"])

        # Démarre le serveur
        manager.start_server(server)

        # Crée l'entrée d'historique
        ServerStatus.objects.create(server=server, status=ServerInstance.RUNNING, message="Serveur démarré avec succès")

        logger.info(f"Serveur {server.name} démarré avec succès")

    except Exception as e:
        logger.error(f"Erreur lors du démarrage du serveur {server_id}: {e}")

        # Met à jour le statut en erreur
        try:
            server = ServerInstance.objects.get(id=server_id)
            server.status = "error"
            server.save(update_fields=["status"])

            ServerStatus.objects.create(server=server, status="error", message=f"Erreur lors du démarrage: {str(e)}")
        except:
            pass

        # Retry si possible
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def stop_server_task(self, server_id: int, user_id: int = None):
    """
    Tâche asynchrone pour arrêter un serveur

    Args:
        server_id: ID du serveur
        user_id: ID de l'utilisateur qui arrête (optionnel)
    """
    try:
        from accounts.models import User
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance, ServerStatus

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        # Change le statut
        server.status = "stopping"
        server.save(update_fields=["status"])

        # Arrête le serveur
        manager.stop_server(server)

        # Crée l'entrée d'historique
        triggered_by = User.objects.get(id=user_id) if user_id else None
        ServerStatus.objects.create(
            server=server, status=ServerInstance.STOPPED, message="Serveur arrêté", triggered_by=triggered_by
        )

        logger.info(f"Serveur {server.name} arrêté avec succès")

    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt du serveur {server_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def restart_server_task(self, server_id: int, user_id: int = None):
    """
    Tâche asynchrone pour redémarrer un serveur

    Args:
        server_id: ID du serveur
        user_id: ID de l'utilisateur qui redémarre (optionnel)
    """
    try:
        from accounts.models import User
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance, ServerStatus

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        # Change le statut
        server.status = "stopping"
        server.save(update_fields=["status"])

        # Redémarre le serveur
        manager.restart_server(server)

        # Crée l'entrée d'historique
        triggered_by = User.objects.get(id=user_id) if user_id else None
        ServerStatus.objects.create(
            server=server, status=ServerInstance.RUNNING, message="Serveur redémarré", triggered_by=triggered_by
        )

        logger.info(f"Serveur {server.name} redémarré avec succès")

    except Exception as e:
        logger.error(f"Erreur lors du redémarrage du serveur {server_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def update_server_task(self, server_id: int, new_version_id: int = None, user_id: int = None):
    """
    Tâche asynchrone pour mettre à jour un serveur

    Args:
        server_id: ID du serveur
        new_version_id: ID de la nouvelle version (optionnel)
        user_id: ID de l'utilisateur (optionnel)
    """
    try:
        from accounts.models import User
        from docker_manager.services.server_manager import get_server_manager
        from games.models import GameVersion
        from servers.models import ServerInstance, ServerStatus

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        # Change le statut
        server.status = "updating"
        server.save(update_fields=["status"])

        # Récupère la nouvelle version si fournie
        new_version = None
        if new_version_id:
            new_version = GameVersion.objects.get(id=new_version_id)

        # Met à jour le serveur
        manager.update_server(server, new_version)

        # Crée l'entrée d'historique
        triggered_by = User.objects.get(id=user_id) if user_id else None
        version_msg = f" vers {new_version.version}" if new_version else ""
        ServerStatus.objects.create(
            server=server,
            status=ServerInstance.STOPPED,
            message=f"Serveur mis à jour{version_msg}",
            triggered_by=triggered_by,
        )

        logger.info(f"Serveur {server.name} mis à jour avec succès")

    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du serveur {server_id}: {e}")

        try:
            server = ServerInstance.objects.get(id=server_id)
            server.status = "error"
            server.save(update_fields=["status"])
        except:
            pass

        raise self.retry(exc=e, countdown=120)


@shared_task
def collect_server_metrics():
    """
    Collecte les métriques de tous les serveurs en cours d'exécution
    Exécutée toutes les 30 secondes
    """
    try:
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance, ServerMetrics

        manager = get_server_manager()
        running_servers = ServerInstance.objects.filter(status=ServerInstance.RUNNING)

        for server in running_servers:
            try:
                stats = manager.get_server_stats(server)

                if stats:
                    ServerMetrics.objects.create(
                        server=server,
                        cpu_usage=stats.get("cpu_percent", 0),
                        memory_usage=stats.get("memory_usage", 0),
                        memory_percent=stats.get("memory_percent", 0),
                        players_online=stats.get("players_online", 0),
                        uptime_seconds=stats.get("uptime", 0),
                    )

            except Exception as e:
                logger.error(f"Erreur collecte metrics pour {server.name}: {e}")

        logger.info(f"Métriques collectées pour {running_servers.count()} serveurs")

    except Exception as e:
        logger.error(f"Erreur lors de la collecte des métriques: {e}")


@shared_task
def check_auto_update_servers():
    """
    Vérifie et met à jour les serveurs avec auto_update=True
    Exécutée quotidiennement à 4h du matin
    """
    try:
        from games.models import GameVersion
        from servers.models import ServerInstance

        servers = ServerInstance.objects.filter(auto_update=True, status=ServerInstance.STOPPED)

        for server in servers:
            try:
                # Vérifie s'il y a une version recommandée plus récente
                recommended = (
                    GameVersion.objects.filter(game=server.game, is_recommended=True, is_stable=True)
                    .order_by("-release_date")
                    .first()
                )

                if recommended and recommended != server.game_version:
                    logger.info(f"Mise à jour auto de {server.name} vers {recommended.version}")

                    # Lance la mise à jour
                    update_server_task.delay(server_id=server.id, new_version_id=recommended.id)

            except Exception as e:
                logger.error(f"Erreur auto-update pour {server.name}: {e}")

        logger.info(f"Vérification auto-update terminée pour {servers.count()} serveurs")

    except Exception as e:
        logger.error(f"Erreur lors de la vérification auto-update: {e}")


@shared_task
def cleanup_old_metrics():
    """
    Nettoie les anciennes métriques (> 7 jours)
    Exécutée quotidiennement
    """
    try:
        from datetime import timedelta

        from servers.models import ServerMetrics

        cutoff_date = timezone.now() - timedelta(days=7)
        deleted_count = ServerMetrics.objects.filter(created_at__lt=cutoff_date).delete()[0]

        logger.info(f"{deleted_count} anciennes métriques supprimées")

    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des métriques: {e}")


@shared_task
def cleanup_old_status_history():
    """
    Nettoie l'ancien historique des statuts (> 30 jours)
    Exécutée hebdomadairement
    """
    try:
        from datetime import timedelta

        from servers.models import ServerStatus

        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = ServerStatus.objects.filter(created_at__lt=cutoff_date).delete()[0]

        logger.info(f"{deleted_count} anciens statuts supprimés")

    except Exception as e:
        logger.error(f"Erreur lors du nettoyage de l'historique: {e}")


@shared_task
def sync_container_status():
    """
    Synchronise le statut des serveurs avec Docker
    """
    try:
        from docker_manager.services.docker_service import get_docker_service
        from servers.models import ServerInstance

        docker_service = get_docker_service()
        servers = ServerInstance.objects.exclude(container_id__isnull=True)

        for server in servers:
            try:
                docker_status = docker_service.get_container_status(server.container_id)

                # Mapping Docker -> Django status
                status_map = {"running": "running", "exited": "stopped", "dead": "error", "not_found": "error"}

                new_status = status_map.get(docker_status, "error")

                if server.status != new_status:
                    with transaction.atomic():
                        server.status = new_status
                        ServerStatus.objects.create(
                            server=server, status=new_status, message=f"Transition vers {new_status}"
                        )
                        server.save(update_fields=["status"])
                        logger.info(f"Statut synchronisé pour {server.name}: {new_status}")

            except Exception as e:
                logger.error(f"Erreur sync status pour {server.name}: {e}")

    except Exception as e:
        logger.error(f"Erreur lors de la synchronisation des statuts: {e}")


@shared_task
def install_mod_task(server_id: int, mod_id: int):
    """
    Tâche asynchrone pour installer un mod

    Args:
        server_id: ID du serveur
        mod_id: ID du mod
    """
    try:
        from docker_manager.services.server_manager import get_server_manager
        from games.models import GameMod
        from servers.models import ServerInstance, ServerMod

        server = ServerInstance.objects.get(id=server_id)
        mod = GameMod.objects.get(id=mod_id)
        manager = get_server_manager()

        # Installe le mod
        manager.install_mod(server, mod)

        # Crée l'entrée ServerMod si elle n'existe pas
        ServerMod.objects.get_or_create(server=server, mod=mod, defaults={"is_enabled": True})

        logger.info(f"Mod {mod.name} installé sur {server.name}")

    except Exception as e:
        logger.error(f"Erreur lors de l'installation du mod: {e}")
        raise


@shared_task
def uninstall_mod_task(server_id: int, mod_id: int):
    """
    Tâche asynchrone pour désinstaller un mod

    Args:
        server_id: ID du serveur
        mod_id: ID du mod
    """
    try:
        from docker_manager.services.server_manager import get_server_manager
        from games.models import GameMod
        from servers.models import ServerInstance, ServerMod

        server = ServerInstance.objects.get(id=server_id)
        mod = GameMod.objects.get(id=mod_id)
        manager = get_server_manager()

        # Désinstalle le mod
        manager.uninstall_mod(server, mod)

        # Supprime l'entrée ServerMod
        ServerMod.objects.filter(server=server, mod=mod).delete()

        logger.info(f"Mod {mod.name} désinstallé de {server.name}")

    except Exception as e:
        logger.error(f"Erreur lors de la désinstallation du mod: {e}")
        raise
