import logging

from celery import shared_task
from django.utils import timezone
from django.db import transaction

from servers.models import ServerStatus

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def start_server_task(self, server_id: int):
    """
    Async task to start a server

    Args:
        server_id: ID of the server to start
    """
    try:
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance, ServerStatus

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        # Change status
        server.status = "starting"
        server.save(update_fields=["status"])

        # Start the server
        manager.start_server(server)

        # Create history entry
        ServerStatus.objects.create(server=server, status=ServerInstance.RUNNING, message="Serveur démarré avec succès")

        logger.info(f"Serveur {server.name} démarré avec succès")

    except Exception as e:
        logger.error(f"Erreur lors du démarrage du serveur {server_id}: {e}")

        # Update status to error
        try:
            server = ServerInstance.objects.get(id=server_id)
            server.status = "error"
            server.save(update_fields=["status"])

            ServerStatus.objects.create(server=server, status="error", message=f"Erreur lors du démarrage: {str(e)}")
        except:
            pass

        # Retry if possible
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def stop_server_task(self, server_id: int, user_id: int = None):
    """
    Async task to stop a server

    Args:
        server_id: Server ID
        user_id: ID of the user stopping the server (optional)
    """
    try:
        from accounts.models import User
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance, ServerStatus

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        # Change status
        server.status = "stopping"
        server.save(update_fields=["status"])

        # Stop the server
        manager.stop_server(server)

        # Create history entry
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
    Async task to restart a server

    Args:
        server_id: Server ID
        user_id: ID of the user restarting the server (optional)
    """
    try:
        from accounts.models import User
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance, ServerStatus

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        # Change status
        server.status = "stopping"
        server.save(update_fields=["status"])

        # Restart the server
        manager.restart_server(server)

        # Create history entry
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
    Async task to update a server

    Args:
        server_id: Server ID
        new_version_id: ID of the new version (optional)
        user_id: User ID (optional)
    """
    try:
        from accounts.models import User
        from docker_manager.services.server_manager import get_server_manager
        from games.models import GameVersion
        from servers.models import ServerInstance, ServerStatus

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        # Change status
        server.status = "updating"
        server.save(update_fields=["status"])

        # Get the new version if provided
        new_version = None
        if new_version_id:
            new_version = GameVersion.objects.get(id=new_version_id)

        # Update the server
        manager.update_server(server, new_version)

        # Create history entry
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
    Collect metrics from all running servers
    Executed every 30 seconds
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
    Check and update servers with auto_update=True
    Executed daily at 4 AM
    """
    try:
        from games.models import GameVersion
        from servers.models import ServerInstance

        servers = ServerInstance.objects.filter(auto_update=True, status=ServerInstance.STOPPED)

        for server in servers:
            try:
                # Check if there is a newer recommended version
                recommended = (
                    GameVersion.objects.filter(game=server.game, is_recommended=True, is_stable=True)
                    .order_by("-release_date")
                    .first()
                )

                if recommended and recommended != server.game_version:
                    logger.info(f"Auto-updating {server.name} to {recommended.version}")

                    # Launch the update
                    update_server_task.delay(server_id=server.id, new_version_id=recommended.id)

            except Exception as e:
                logger.error(f"Erreur auto-update pour {server.name}: {e}")

        logger.info(f"Vérification auto-update terminée pour {servers.count()} serveurs")

    except Exception as e:
        logger.error(f"Erreur lors de la vérification auto-update: {e}")


@shared_task
def cleanup_old_metrics():
    """
    Clean up old metrics (> 7 days)
    Executed daily
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
    Clean up old status history (> 30 days)
    Executed weekly
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
    Synchronize server status with Docker
    """
    try:
        from docker_manager.services.docker_service import get_docker_service
        from servers.models import ServerInstance

        docker_service = get_docker_service()
        servers = ServerInstance.objects.exclude(container_id__isnull=True)

        for server in servers:
            try:
                docker_status = docker_service.get_container_status(server.container_id)

                # Docker -> Django status mapping
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
    Async task to install a mod

    Args:
        server_id: Server ID
        mod_id: Mod ID
    """
    try:
        from docker_manager.services.server_manager import get_server_manager
        from games.models import GameMod
        from servers.models import ServerInstance, ServerMod

        server = ServerInstance.objects.get(id=server_id)
        mod = GameMod.objects.get(id=mod_id)
        manager = get_server_manager()

        # Install the mod
        manager.install_mod(server, mod)

        # Create ServerMod entry if it doesn't exist
        ServerMod.objects.get_or_create(server=server, mod=mod, defaults={"is_enabled": True})

        logger.info(f"Mod {mod.name} installé sur {server.name}")

    except Exception as e:
        logger.error(f"Erreur lors de l'installation du mod: {e}")
        raise


@shared_task
def uninstall_mod_task(server_id: int, mod_id: int):
    """
    Async task to uninstall a mod

    Args:
        server_id: Server ID
        mod_id: Mod ID
    """
    try:
        from docker_manager.services.server_manager import get_server_manager
        from games.models import GameMod
        from servers.models import ServerInstance, ServerMod

        server = ServerInstance.objects.get(id=server_id)
        mod = GameMod.objects.get(id=mod_id)
        manager = get_server_manager()

        # Uninstall the mod
        manager.uninstall_mod(server, mod)

        # Delete the ServerMod entry
        ServerMod.objects.filter(server=server, mod=mod).delete()

        logger.info(f"Mod {mod.name} désinstallé de {server.name}")

    except Exception as e:
        logger.error(f"Erreur lors de la désinstallation du mod: {e}")
        raise
