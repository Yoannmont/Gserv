import logging
import os
import traceback

import docker
from django.conf import settings
from django.utils import timezone

from docker_manager.services.docker_service import (
    DockerServiceError,
    get_docker_service,
)
from servers.models import ServerInstance

logger = logging.getLogger(__name__)


class ServerManager:
    """High-level manager for game servers"""

    def __init__(self):
        self.docker_service = get_docker_service()
        self.base_path = settings.SERVERS_DATA_PATH

    def create_server(self, server_instance) -> str:
        """
        Create a complete game server

        Args:
            server_instance: ServerInstance instance (Django model)

        Returns:
            container_id: ID of the created container
        """
        try:
            logger.info(f"[server_manager] Creating server {server_instance.name}")

            # Create data directories
            server_path = self._create_server_directories(server_instance)

            # Prepare configuration
            ports = self._prepare_ports(server_instance)
            environment = self._prepare_environment(server_instance)
            volumes = self._prepare_volumes(server_instance, server_path)

            # Get resources
            config = server_instance.configuration
            memory_limit = config.memory_limit if hasattr(server_instance, "configuration") else "2g"
            cpu_limit = config.cpu_limit if hasattr(server_instance, "configuration") else 2.0

            # Create Docker container
            container_id = self.docker_service.create_container(
                image=self._get_docker_image(server_instance),
                name=f"server_{server_instance.id}_{server_instance.game.slug}",
                ports=ports,
                environment=environment,
                volumes=volumes,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
            )

            logger.info(f"[server_manager] Server {server_instance.name} created with container_id: {container_id}")
            return container_id

        except Exception:
            logger.error(
                "[server_manager] Error during server creation: %r",
                traceback.format_exc(),
            )
            raise

    def start_server(self, server_instance) -> bool:
        """
        Start a server

        Args:
            server_instance: ServerInstance instance

        Returns:
            True if started successfully
        """
        try:
            if not server_instance.container_id:
                raise ValueError("Server has no container_id")

            logger.info(f"[server_manager] Starting server {server_instance.name}")

            # Start the container
            self.docker_service.start_container(server_instance.container_id)

            # Update timestamp
            server_instance.last_started_at = timezone.now()
            server_instance.status = ServerInstance.RUNNING
            server_instance.save(update_fields=["last_started_at", "status"])

            return True

        except DockerServiceError as e:
            logger.error("[server_manager] Docker error during server start: %r", e)
            server_instance.status = ServerInstance.ERROR
            server_instance.save(update_fields=["status"])
            raise

    def stop_server(self, server_instance, timeout: int = settings.SERVER_STOP_TIMEOUT) -> bool:
        """
        Stop a server

        Args:
            server_instance: ServerInstance instance
            timeout: Timeout before force kill

        Returns:
            True if stopped successfully
        """
        try:
            if not server_instance.container_id:
                raise ValueError("Server has no container_id")

            logger.info(f"[server_manager] Stopping server {server_instance.name}")

            # Stop the container
            self.docker_service.stop_container(server_instance.container_id, timeout)

            server_instance.status = ServerInstance.STOPPED
            server_instance.save(update_fields=["status"])

            return True

        except DockerServiceError as e:
            logger.error("[server_manager] Docker error during server stop: %r", e)
            raise

    def restart_server(self, server_instance, timeout: int = settings.SERVER_RESTART_TIMEOUT) -> bool:
        """
        Restart a server

        Args:
            server_instance: ServerInstance instance
            timeout: Timeout

        Returns:
            True if restarted successfully
        """
        try:
            if not server_instance.container_id:
                raise ValueError("Server has no container_id")

            logger.info(f"[server_manager] Restarting server {server_instance.name}")

            self.docker_service.restart_container(server_instance.container_id, timeout)

            server_instance.last_started_at = timezone.now()
            server_instance.status = ServerInstance.RUNNING
            server_instance.save(update_fields=["last_started_at", "status"])

            return True

        except DockerServiceError as e:
            logger.error("[server_manager] Docker error during server restart: %r", e)
            server_instance.status = "error"
            server_instance.save(update_fields=["status"])
            raise

    def update_server(self, server_instance, new_version=None) -> str:
        """
        Update a server to a new version

        Args:
            server_instance: ServerInstance instance
            new_version: New GameVersion (optional)

        Returns:
            New container_id
        """
        try:
            logger.info(f"[server_manager] Updating server {server_instance.name}")

            # Stop the server
            if server_instance.is_running:
                self.stop_server(server_instance)

            # Determine the new image
            if new_version:
                server_instance.game_version = new_version
                server_instance.save(update_fields=["game_version"])

            new_image = self._get_docker_image(server_instance)

            # Update the container
            new_container_id = self.docker_service.update_container(
                container_id=server_instance.container_id,
                image=new_image,
                preserve_data=True,
            )

            server_instance.container_id = new_container_id
            server_instance.status = ServerInstance.STOPPED
            server_instance.save(update_fields=["container_id", "status"])

            logger.info(f"[server_manager] Server {server_instance.name} updated")
            return new_container_id

        except DockerServiceError as e:
            logger.error("[server_manager] Error during server update: %r", e)
            server_instance.status = ServerInstance.ERROR
            server_instance.save(update_fields=["status"])
            raise

    def delete_server(self, server_instance, delete_data: bool = False) -> bool:
        """
        Delete a server

        Args:
            server_instance: ServerInstance instance
            delete_data: Also delete data files

        Returns:
            True if deleted successfully
        """
        try:
            logger.info(f"[server_manager] Deleting server {server_instance.name}")
            container_id = server_instance.container_id

            if container_id:
                # Stop and remove the container
                try:
                    self.docker_service.stop_container(container_id)
                except docker.errors.NotFound:
                    logger.warning(
                        "[server_manager] Couldn't find container %s to stop it. Skipping",
                        server_instance,
                    )

                self.docker_service.remove_container(container_id, force=True, volumes=delete_data)

            # Delete files if requested
            if delete_data:
                server_path = self._get_server_path(server_instance)
                if os.path.exists(server_path):
                    import shutil

                    shutil.rmtree(server_path)
                    logger.info(f"[server_manager] Server data deleted: {server_path}")

            return True

        except DockerServiceError as e:
            logger.error("[server_manager] Error during server deletion: %r", e)
            raise

    def get_server_stats(self, server_instance) -> dict:
        """
        Get server statistics

        Args:
            server_instance: ServerInstance instance

        Returns:
            Dictionary of statistics
        """
        try:
            if not server_instance.container_id:
                return {}

            stats = self.docker_service.get_container_stats(server_instance.container_id)

            # Add game-specific information
            stats["players_online"] = self._get_players_count(server_instance)
            stats["uptime"] = self._get_uptime(server_instance)

            return stats

        except DockerServiceError:
            return {}

    def check_server_health(self, server_instance) -> str:
        """
        Check server health using health check command or container status

        Args:
            server_instance: ServerInstance instance

        Returns:
            Django status (RUNNING, ERROR, STOPPED, etc.)
        """
        try:
            if not server_instance.container_id:
                return ServerInstance.ERROR

            docker_status = self.docker_service.get_container_status(server_instance.container_id)

            # Mapping Docker -> Django status
            status_map = {
                "running": ServerInstance.RUNNING,
                "exited": ServerInstance.STOPPED,
                "dead": ServerInstance.ERROR,
                "not_found": ServerInstance.ERROR,
                "created": ServerInstance.CREATED,
                "restarting": ServerInstance.STARTING,
                "paused": ServerInstance.STOPPED,
            }

            if docker_status != "running":
                return status_map.get(docker_status, ServerInstance.ERROR)

            game = server_instance.game

            if game.health_check_command:
                try:
                    exit_code, output = self.docker_service.execute_command_with_exit_code(
                        server_instance.container_id, game.health_check_command
                    )

                    if exit_code == 0:
                        logger.debug(f"[server_manager] Health check passed for {server_instance.name}: {output[:100]}")
                        return ServerInstance.RUNNING
                    else:
                        logger.warning(
                            f"[server_manager] Health check failed for {server_instance.name} "
                            f"(exit_code={exit_code}): {output[:100]}"
                        )
                        return ServerInstance.ERROR

                except DockerServiceError as e:
                    logger.error(
                        f"[server_manager] Health check command failed for {server_instance.name}: %r",
                        e,
                    )
                    return ServerInstance.ERROR

            return ServerInstance.RUNNING

        except Exception as e:
            logger.error(
                f"[server_manager] Error during health check for {server_instance.name}: %r",
                e,
            )
            return ServerInstance.ERROR

    def delete_unused_containers(self):
        """
        Delete unused containers
        """
        known_containers = ServerInstance.objects.values_list("container_id", flat=True)
        containers = self.docker_service.list_containers(all=True)
        for container in containers:
            if container["id"] not in known_containers:
                self.docker_service.remove_container(container["id"], force=True, volumes=False)
                logger.info(f"[server_manager] Deleted unused container: {container['id']}")

    # Private methods

    def _create_server_directories(self, server_instance) -> str:
        """Create necessary directories for a server"""
        server_path = self._get_server_path(server_instance)

        directories = [
            server_path,
            os.path.join(server_path, "data"),
            os.path.join(server_path, "config"),
            os.path.join(server_path, "backups"),
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)

        logger.info(f"[server_manager] Directories created for {server_instance.name}: {server_path}")
        return server_path

    def _get_server_path(self, server_instance) -> str:
        """Return the server path"""
        return os.path.join(self.base_path, server_instance.game.slug, str(server_instance.id))

    def _get_docker_image(self, server_instance) -> str:
        """Build the full Docker image name"""
        game = server_instance.game
        version = server_instance.game_version

        # If the version has a specific Docker tag
        if version.docker_tag:
            return f"{game.docker_image}:{version.docker_tag}"

        # Otherwise use the docker image name only
        return f"{game.docker_image}"

    def _prepare_ports(self, server_instance) -> dict:
        """Prepare port mapping"""
        return server_instance.get_all_port_mappings()

    def _prepare_environment(self, server_instance) -> dict:
        """Prepare environment variables"""
        env = {}

        if hasattr(server_instance, "configuration"):
            config = server_instance.configuration
            env.update(config.environment_variables)

        # Add common variables
        env["SERVER_NAME"] = server_instance.name
        env["MAX_PLAYERS"] = str(server_instance.max_players)

        return env

    def _prepare_volumes(self, server_instance, server_path: str) -> dict:
        """Prepare Docker volumes"""
        config = server_instance.configuration
        volumes_info = config.docker_volumes
        return {os.path.join(server_path, key): volumes_info[key] for key in volumes_info}

    def _get_players_count(self, server_instance) -> int:
        """Get the number of connected players"""
        # TODO: Implement based on game type
        # For Minecraft: query RCON or parse logs
        # For Palworld: specific API
        return 0

    def _get_uptime(self, server_instance) -> int:
        """Get uptime in seconds"""
        if not server_instance.last_started_at:
            return 0

        delta = timezone.now() - server_instance.last_started_at
        return int(delta.total_seconds())


# Singleton instance
_server_manager = None


def get_server_manager() -> ServerManager:
    """Return the singleton instance of the server manager"""
    global _server_manager
    if _server_manager is None:
        _server_manager = ServerManager()
    return _server_manager
