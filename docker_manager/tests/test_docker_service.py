"""
Tests for DockerService using mock Docker client
"""

from collections.abc import Generator

import docker
import pytest

from docker_manager.services.docker_service import (
    DockerServiceError,
    get_docker_service,
)


@pytest.mark.django_db
class TestDockerService:
    def test_create_container(self, patched_docker_service):
        docker_service = get_docker_service()

        container_id = docker_service.create_container(
            image="test/image:latest",
            name="test_server",
            ports={"25565/tcp": 25565},
            environment={"EULA": "TRUE"},
            volumes={"/data": {"bind": "/data", "mode": "rw"}},
            memory_limit="2g",
            cpu_limit=2.0,
        )

        assert container_id is not None
        assert len(container_id) == 64

        container = patched_docker_service.containers.get(container_id)
        assert container.name == "test_server"
        assert container.status == "created"

    def test_start_container(self, patched_docker_service, fake_container):
        docker_service = get_docker_service()

        result = docker_service.start_container(fake_container.id)
        assert result is True

        container = patched_docker_service.containers.get(fake_container.id)
        assert container.status == "running"

    def test_stop_container(self, patched_docker_service, fake_container):
        docker_service = get_docker_service()

        result = docker_service.start_container(fake_container.id)
        assert result is True

        result = docker_service.stop_container(fake_container.id)
        assert result is True

        container = patched_docker_service.containers.get(fake_container.id)
        assert container.status == "exited"

    def test_get_container_status(self, patched_docker_service, fake_container):
        docker_service = get_docker_service()

        status = docker_service.get_container_status(fake_container.id)
        assert status == "created"

        docker_service.start_container(fake_container.id)
        status = docker_service.get_container_status(fake_container.id)
        assert status == "running"

    def test_get_container_logs(self, patched_docker_service, fake_container):
        docker_service = get_docker_service()

        docker_service.start_container(fake_container.id)
        docker_service.stop_container(fake_container.id)
        docker_service.start_container(fake_container.id)

        logs = docker_service.get_container_logs(fake_container.id, tail=10, timestamps=True)

        assert logs == (
            "2024-01-01T12:00:00.000000000Z - Container started\n"
            "2024-01-01T12:00:00.000000000Z - Container stopped\n"
            "2024-01-01T12:00:00.000000000Z - Container started"
        )

    def test_stream_container_logs(self, patched_docker_service, fake_container):
        docker_service = get_docker_service()

        docker_service.start_container(fake_container.id)
        docker_service.stop_container(fake_container.id)
        docker_service.start_container(fake_container.id)

        log_generator = docker_service.stream_container_logs(fake_container.id, tail=10)
        assert isinstance(log_generator, Generator)
        logs = list(log_generator)

        assert logs == [
            "2024-01-01T12:00:00.000000000Z - Container started",
            "2024-01-01T12:00:00.000000000Z - Container stopped",
            "2024-01-01T12:00:00.000000000Z - Container started",
        ]

    def test_get_container_stats(self, patched_docker_service, fake_container):
        docker_service = get_docker_service()

        docker_service.start_container(fake_container.id)

        stats = docker_service.get_container_stats(fake_container.id)
        assert "cpu_percent" in stats
        assert "memory_usage" in stats
        assert "memory_limit" in stats
        assert stats["memory_limit"] > 0

    def test_container_not_found(self, patched_docker_service):
        docker_service = get_docker_service()

        status = docker_service.get_container_status("nonexistent")
        assert status == "not_found"

        with pytest.raises(docker.errors.NotFound):
            docker_service.get_container_stats("nonexistent")

    def test_remove_container(self, patched_docker_service, fake_container):
        docker_service = get_docker_service()

        # Remove stopped container
        result = docker_service.remove_container(fake_container.id)
        assert result is True

        status = docker_service.get_container_status(fake_container.id)
        assert status == "not_found"

        # already removed
        result = docker_service.remove_container(fake_container.id)
        assert result is True

        with pytest.raises(DockerServiceError):
            docker_service.get_container_logs(fake_container.id)

    def test_list_containers(self, patched_docker_service):
        docker_service = get_docker_service()

        container_id1 = docker_service.create_container(
            image="test/image:latest",
            name="server1",
            ports={"25565/tcp": 25565},
            environment={},
            volumes={},
        )
        docker_service.create_container(
            image="test/image:latest",
            name="server2",
            ports={"25566/tcp": 25566},
            environment={},
            volumes={},
        )  # not running

        docker_service.start_container(container_id1)

        containers = docker_service.list_containers(all=True)
        assert len(containers) == 2

        running = docker_service.list_containers(all=False)
        assert len(running) == 1
        assert running[0]["id"] == container_id1
