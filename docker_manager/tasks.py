import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from servers.models import ServerStatus

beat_logger = logging.getLogger("celery_beat")
worker_logger = logging.getLogger("celery_worker")


@shared_task(bind=True, max_retries=3)
def create_server_task(self, server_id):
    """
    Async task to create a server

    Args:
        server_id: ID of the server to create
    """
    try:
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        # Create the server
        container_id = manager.create_server(server)
        server.container_id = container_id
        server.save(update_fields=["container_id"])

        worker_logger.info(f"[docker_manager] Server {server.name} created with container_id: {server.container_id}")

    except Exception as e:
        worker_logger.error("[docker_manager] Task create failed for server_id=%s: %r", server_id, e)
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def start_server_task(self, server_id: int, user_id: int = None):
    """
    Async task to start a server

    Args:
        server_id: ID of the server to start
    """
    try:
        from accounts.models import User
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance, ServerStatus

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        triggered_by = User.objects.get(id=user_id) if user_id else None
        # Change status
        server.status = ServerInstance.STARTING
        server.save(update_fields=["status"])

        # Start the server
        manager.start_server(server)

        # Create history entry
        ServerStatus.objects.create(
            server=server, status=ServerInstance.STARTED, message="Serveur démarré avec succès", triggered_by=triggered_by
        )

        worker_logger.info(f"[docker_manager] Server {server.name} started with container_id: {server.container_id}")

    except Exception as e:
        worker_logger.error("[docker_manager] Task start failed for server_id=%s: %r", server_id, e)

        # Update status to error
        try:
            server = ServerInstance.objects.get(id=server_id)
            server.status = ServerInstance.ERROR
            server.save(update_fields=["status"])

            ServerStatus.objects.create(server=server, status="error", message=f"Erreur lors du démarrage: {str(e)}")
        except Exception as e:
            worker_logger.critical("[docker_manager] Task start failed for server_id=%s : %r", server_id, e)

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

        triggered_by = User.objects.get(id=user_id) if user_id else None
        # Change status
        server.status = ServerInstance.STOPPING
        server.save(update_fields=["status"])

        # Stop the server
        manager.stop_server(server)

        # Create history entry

        ServerStatus.objects.create(
            server=server, status=ServerInstance.STOPPED, message="Serveur arrêté", triggered_by=triggered_by
        )

        worker_logger.info(f"[docker_manager] Server {server.name} stopped with container_id: {server.container_id}")

    except Exception as e:
        worker_logger.error("[docker_manager] Task stop failed for server_id=%s: %r", server_id, e)
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

        triggered_by = User.objects.get(id=user_id) if user_id else None
        # Change status
        server.status = ServerInstance.STOPPING
        server.save(update_fields=["status"])

        # Restart the server
        manager.restart_server(server)

        # Create history entry

        ServerStatus.objects.create(
            server=server, status=ServerInstance.STARTED, message="Serveur redémarré", triggered_by=triggered_by
        )

        worker_logger.info(f"[docker_manager] Server {server.name} restarted with container_id: {server.container_id}")

    except Exception as e:
        worker_logger.error(f"Erreur lors du redémarrage du serveur {server_id}: {e}")
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
        triggered_by = User.objects.get(id=user_id) if user_id else None
        # Change status
        server.status = ServerInstance.UPDATING
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

        worker_logger.info(f"[docker_manager] Server {server.name} updated with container_id: {server.container_id}")

    except Exception as e:
        worker_logger.error("[docker_manager] Task update failed for server_id=%s: %r", server_id, e)

        try:
            server = ServerInstance.objects.get(id=server_id)
            server.status = ServerInstance.ERROR
            server.save(update_fields=["status"])
        except ServerInstance.DoesNotExist:
            worker_logger.critical("[docker_manager] Task update failed for server_id=%s because does not exist", server_id, e)

        raise self.retry(exc=e, countdown=120)


@shared_task(bind=True, max_retries=3)
def full_reset_server_task(self, server_id: int, delete_data: bool = False, user_id: int = None):
    """
    Async task to full reset a server

    Args:
        server_id: Server ID
        delete_data: If True, delete server data
        user_id: User ID (optional)
    """
    try:
        from accounts.models import User
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance, ServerStatus

        server = ServerInstance.objects.get(id=server_id)
        manager = get_server_manager()

        triggered_by = User.objects.get(id=user_id) if user_id else None
        manager.delete_server(server, delete_data=delete_data)
        container_id = manager.create_server(server)
        server.container_id = container_id
        server.save(update_fields=["container_id"])

        manager.start_server(server)

        ServerStatus.objects.create(
            server=server, status=ServerInstance.STARTED, message="Serveur remis à zéro et relancé", triggered_by=triggered_by
        )

        worker_logger.info(f"[docker_manager] Server {server.name} full reset with container_id: {server.container_id}")
    except Exception as e:
        worker_logger.error("[docker_manager] Task full reset failed for server_id=%s: %r", server_id, e)
        raise self.retry(exc=e, countdown=60)


@shared_task
def collect_server_metrics():
    """
    Collect metrics from all running servers
    """
    try:
        from docker_manager.services.server_manager import get_server_manager
        from servers.models import ServerInstance, ServerMetrics

        manager = get_server_manager()
        running_servers = ServerInstance.objects.filter(status=ServerInstance.STARTED)

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
                beat_logger.error(f"[docker_manager] Error during metrics collection for server {server.name}: %r", e)

        beat_logger.info(f"[docker_manager] Metrics collected for {running_servers.count()} servers")

    except Exception as e:
        beat_logger.error("[docker_manager] Error during metrics collection: %r", e)


@shared_task
def check_auto_update_servers():
    """
    Check and update servers with auto_update=True
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
                    beat_logger.info(f"[docker_manager] Auto-updating {server.name} to {recommended.version}")

                    # Launch the update
                    update_server_task.delay(server_id=server.id, new_version_id=recommended.id)

            except Exception as e:
                beat_logger.error(f"[docker_manager] Error during auto-update for server {server.name}: %r", e)

        beat_logger.info(f"[docker_manager] Auto-update check completed for {servers.count()} servers")

    except Exception as e:
        beat_logger.error("[docker_manager] Error during auto-update check: %r", e)


@shared_task
def cleanup_old_metrics():
    """
    Clean up old metrics (> 7 days)

    """
    try:
        from datetime import timedelta

        from servers.models import ServerMetrics

        cutoff_date = timezone.now() - timedelta(days=7)
        deleted_count = ServerMetrics.objects.filter(created_at__lt=cutoff_date).delete()[0]

        beat_logger.info(f"[docker_manager] {deleted_count} old metrics deleted")

    except Exception as e:
        beat_logger.error("[docker_manager] Error during metrics cleanup: %r", e)


@shared_task
def cleanup_old_status_history():
    """
    Clean up old status history (> 30 days)
    """
    try:
        from datetime import timedelta

        from servers.models import ServerStatus

        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = ServerStatus.objects.filter(created_at__lt=cutoff_date).delete()[0]

        beat_logger.info(f"[docker_manager] {deleted_count} old statuses deleted")

    except Exception as e:
        beat_logger.error("[docker_manager] Error during status history cleanup: %r", e)


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

        beat_logger.info(f"[docker_manager] Synchronizing status for {servers.count()} servers")

        for server in servers:
            try:
                docker_status = docker_service.get_container_status(server.container_id)

                # Docker -> Django status mapping
                status_map = {
                    "running": ServerInstance.STARTED,
                    "exited": ServerInstance.STOPPED,
                    "dead": ServerInstance.ERROR,
                    "not_found": ServerInstance.ERROR,
                }

                new_status = status_map.get(docker_status, ServerInstance.ERROR)

                if server.status != new_status:
                    with transaction.atomic():
                        server.status = new_status
                        ServerStatus.objects.create(server=server, status=new_status, message=f"Transition vers {new_status}")
                        server.save(update_fields=["status"])
                        beat_logger.info(f"[docker_manager] Status synchronized for {server.name}: {new_status}")

            except Exception as e:
                beat_logger.error(f"[docker_manager] Error during status synchronization for server {server.name}: %r", e)

        beat_logger.info(f"[docker_manager] Status synchronization completed for {servers.count()} servers")

    except Exception as e:
        beat_logger.error("[docker_manager] Error during status synchronization: %r", e)