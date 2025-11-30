import logging
from typing import Any

import docker

logger = logging.getLogger(__name__)


class DockerServiceError(Exception):
    """Custom exception for Docker errors"""


class DockerService:
    """Docker container management service"""

    def __init__(self):
        """Initialize connection to Docker daemon"""
        try:
            self.client = docker.from_env()
            # Test connection
            self.client.ping()
            logger.info("[docker_service] Connection to Docker daemon successful")
        except docker.errors.DockerException as e:
            logger.critical("[docker_service] Failed to connect to Docker daemon: %r", e)
            raise DockerServiceError(f"[docker_service] Failed to connect to Docker daemon: {e}")

    def create_container(
        self,
        image: str,
        name: str,
        ports: dict[str, int],
        environment: dict[str, str],
        volumes: dict[str, dict[str, str]],
        memory_limit: str = "2g",
        cpu_limit: float = 2.0,
        restart_policy: dict[str, Any] | None = None,
        detach: bool = True,
    ) -> str:
        """
        Create a Docker container

        Args:
            image: Docker image (e.g., "itzg/minecraft-server:latest")
            name: Container name
            ports: Port mapping {container_port: host_port}
            environment: Environment variables
            volumes: Volumes to mount {host_path: {'bind': container_path, 'mode': 'rw'}}
            memory_limit: Memory limit (e.g., "2g", "4g")
            cpu_limit: CPU limit (number of cores, e.g., 2.0)
            restart_policy: Restart policy
            detach: Run in background

        Returns:
            container_id: ID of the created container
        """
        try:
            logger.info(f"[docker_service] Creating container {name} with image {image}")

            # Pull image if necessary
            self._pull_image(image)

            # Default restart policy
            if restart_policy is None:
                restart_policy = {"Name": "unless-stopped"}

            # Create container
            container = self.client.containers.create(
                image=image,
                name=name,
                ports=ports,
                environment=environment,
                volumes=volumes,
                mem_limit=memory_limit,
                nano_cpus=int(cpu_limit * 1e9),  # Convert to nano CPUs
                restart_policy=restart_policy,
                detach=detach,
                stdin_open=True,
                tty=True,
            )

            logger.info(f"[docker_service] Container {name} created with ID: {container.id}")
            return container.id

        except docker.errors.APIError as e:
            logger.error("[docker_service] Docker API error during creation: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container creation: {e}")
        except Exception as e:
            logger.error("[docker_service] Unexpected error during creation: %r", e)
            raise DockerServiceError(f"[docker_service] Unexpected error during container creation: {e}")

    def start_container(self, container_id: str) -> bool:
        """
        Start a container

        Args:
            container_id: Container ID

        Returns:
            True if started successfully
        """
        try:
            container = self.client.containers.get(container_id)
            container.start()
            logger.info(f"[docker_service] Container {container_id} started")
            return True
        except docker.errors.NotFound:
            logger.error(f"[docker_service] Container {container_id} not found")
            raise DockerServiceError(f"Conteneur {container_id} introuvable")
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container start: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container start: {e}")

    def stop_container(self, container_id: str, timeout: int = 30) -> bool:
        """
        Stop a container

        Args:
            container_id: Container ID
            timeout: Timeout in seconds before force kill

        Returns:
            True if stopped successfully
        """
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"[docker_service] Container {container_id} stopped")
            return True
        except docker.errors.NotFound:
            logger.error(f"[docker_service] Container {container_id} not found")
            raise DockerServiceError(f"[docker_service] Container {container_id} not found")
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container stop: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container stop: {e}")

    def restart_container(self, container_id: str, timeout: int = 30) -> bool:
        """
        Restart a container

        Args:
            container_id: Container ID
            timeout: Timeout before force restart

        Returns:
            True if restarted successfully
        """
        try:
            container = self.client.containers.get(container_id)
            container.restart(timeout=timeout)
            logger.info(f"[docker_service] Container {container_id} restarted")
            return True
        except docker.errors.NotFound:
            logger.error(f"[docker_service] Container {container_id} not found")
            raise DockerServiceError(f"[docker_service] Container {container_id} not found")
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container restart: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container restart: {e}")

    def remove_container(self, container_id: str, force: bool = False, volumes: bool = False) -> bool:
        """
        Remove a container

        Args:
            container_id: Container ID
            force: Force removal even if running
            volumes: Remove associated volumes

        Returns:
            True if removed successfully
        """
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force, v=volumes)
            logger.info(f"[docker_service] Container {container_id} removed")
            return True
        except docker.errors.NotFound:
            logger.warning(f"[docker_service] Container {container_id} already removed")
            return True
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container removal: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container removal: {e}")

    def get_container_status(self, container_id: str) -> str:
        """
        Get container status

        Args:
            container_id: Container ID

        Returns:
            Container status (running, exited, etc.)
        """
        try:
            container = self.client.containers.get(container_id)
            return container.status
        except docker.errors.NotFound:
            return "not_found"
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container status retrieval: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container status retrieval: {e}")

    def get_container_stats(self, container_id: str) -> dict[str, Any]:
        """
        Get container statistics

        Args:
            container_id: Container ID

        Returns:
            Dictionary with CPU, memory, network, etc.
        """
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)

            # Calculate CPU percentage
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * stats["cpu_stats"]["online_cpus"] * 100.0

            # Memory
            memory_usage = stats["memory_stats"]["usage"]
            memory_limit = stats["memory_stats"]["limit"]
            memory_percent = (memory_usage / memory_limit) * 100.0

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage": memory_usage / (1024 * 1024),  # In MB
                "memory_limit": memory_limit / (1024 * 1024),  # In MB
                "memory_percent": round(memory_percent, 2),
                "network_rx": stats["networks"]["eth0"]["rx_bytes"] if "networks" in stats else 0,
                "network_tx": stats["networks"]["eth0"]["tx_bytes"] if "networks" in stats else 0,
            }
        except docker.errors.NotFound:
            raise DockerServiceError(f"Conteneur {container_id} introuvable")
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container stats retrieval: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container stats retrieval: {e}")

    def get_container_logs(self, container_id: str, tail: int = 100, timestamps: bool = True) -> str:
        """
        Get container logs

        Args:
            container_id: Container ID
            tail: Number of last lines
            timestamps: Include timestamps

        Returns:
            Container logs
        """
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=timestamps)
            return logs.decode("utf-8")
        except docker.errors.NotFound:
            raise DockerServiceError(f"[docker_service] Container {container_id} not found")
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container logs retrieval: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container logs retrieval: {e}")

    def stream_container_logs(self, container_id: str, tail: int = 100, timestamps: bool = True):
        """
        Stream container logs in real-time

        Args:
            container_id: Container ID
            tail: Number of initial lines to return
            timestamps: Include timestamps

        Yields:
            Log lines as strings
        """
        try:
            container = self.client.containers.get(container_id)
            log_stream = container.logs(
                stream=True,
                follow=True,
                tail=tail,
                timestamps=timestamps,
            )
            for log_line in log_stream:
                yield log_line.decode("utf-8", errors="replace")
        except docker.errors.NotFound:
            raise DockerServiceError(f"[docker_service] Container {container_id} not found")
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container logs streaming: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container logs streaming: {e}")

    def execute_command(self, container_id: str, command: str) -> str:
        """
        Execute a command in a container

        Args:
            container_id: Container ID
            command: Command to execute

        Returns:
            Command output
        """
        try:
            container = self.client.containers.get(container_id)
            result = container.exec_run(command)
            return result.output.decode("utf-8")
        except docker.errors.NotFound:
            raise DockerServiceError(f"[docker_service] Container {container_id} not found")
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during command execution: %r", e)
            raise DockerServiceError(f"[docker_service] Error during command execution: {e}")

    def update_container(self, container_id: str, image: str, preserve_data: bool = True) -> str:
        """
        Update a container to a new version

        Args:
            container_id: Current container ID
            image: New image
            preserve_data: Preserve data volumes

        Returns:
            New container ID
        """
        try:
            # Get current config
            old_container = self.client.containers.get(container_id)
            config = old_container.attrs

            # Stop and remove the old container
            self.stop_container(container_id)

            # Pull the new image
            self._pull_image(image)

            # Extract configuration
            name = config["Name"].lstrip("/")
            ports = {}
            if config["HostConfig"]["PortBindings"]:
                for container_port, host_config in config["HostConfig"]["PortBindings"].items():
                    ports[container_port] = int(host_config[0]["HostPort"])

            environment = config["Config"]["Env"]
            volumes = config["HostConfig"]["Binds"] if preserve_data else None

            # Remove the old container
            self.remove_container(container_id, force=True, volumes=not preserve_data)

            # Create the new container
            new_container_id = self.create_container(
                image=image,
                name=name,
                ports=ports,
                environment={var.split("=")[0]: var.split("=")[1] for var in environment if "=" in var},
                volumes=volumes or {},
                memory_limit=config["HostConfig"]["Memory"],
                cpu_limit=config["HostConfig"]["NanoCpus"] / 1e9,
            )

            logger.info(f"[docker_service] Container {container_id} updated to {new_container_id}")
            return new_container_id

        except docker.errors.NotFound:
            raise DockerServiceError(f"[docker_service] Container {container_id} not found")
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container update: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container update: {e}")

    def _pull_image(self, image: str) -> None:
        """
        Pull a Docker image if it doesn't exist locally

        Args:
            image: Image name
        """
        try:
            logger.info(f"[docker_service] Checking image {image}")
            self.client.images.pull(image)
            logger.info(f"[docker_service] Image {image} ready")
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during image pull: %r", e)
            raise DockerServiceError(f"[docker_service] Error during image pull: {e}")

    def list_containers(self, all: bool = False) -> list[dict[str, Any]]:
        """
        List all containers

        Args:
            all: Include stopped containers

        Returns:
            List of containers with their info
        """
        try:
            containers = self.client.containers.list(all=all)
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                }
                for c in containers
            ]
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container listing: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container listing: {e}")

    def cleanup_unused_containers(self) -> int:
        """
        Clean up unused containers

        Returns:
            Number of containers removed
        """
        try:
            removed = self.client.containers.prune()
            count = len(removed["ContainersDeleted"] or [])
            logger.info(f"[docker_service] {count} unused containers removed")
            return count
        except docker.errors.APIError as e:
            logger.error("[docker_service] Error during container cleanup: %r", e)
            raise DockerServiceError(f"[docker_service] Error during container cleanup: {e}")


# Singleton instance
_docker_service = None


def get_docker_service() -> DockerService:
    """Return the singleton instance of the Docker service"""
    global _docker_service
    if _docker_service is None:
        _docker_service = DockerService()
    return _docker_service
