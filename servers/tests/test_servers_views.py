from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from accounts.tests.accounts_factories import UserFactory
from docker_manager.tasks import restart_server_task, start_server_task, stop_server_task, update_server_task
from games.tests.games_factories import GameFactory, GameVersionFactory
from servers.models import ServerInstance
from servers.tests.servers_factories import (
    ServerInstanceFactory,
    ServerPlayerFactory,
)


@pytest.mark.django_db
class TestServerInstanceViewSet:
    def test_list_servers_as_owner(self, authenticated_client, user, patched_docker_service, fake_container):
        ServerInstanceFactory.create_batch(3, owner=user)
        ServerInstanceFactory(container_id=fake_container.id)

        url = reverse("server-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_list_public_servers(self, authenticated_client, user):
        ServerInstanceFactory.create_batch(2, owner=user)
        ServerInstanceFactory(is_public=True)
        ServerInstanceFactory(is_public=False)

        url = reverse("server-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_list_servers_as_admin(self, admin_client, patched_docker_service, fake_container):
        ServerInstanceFactory.create_batch(5, container_id=fake_container.id)

        url = reverse("server-list")
        response = admin_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 5

    def test_create_server(self, authenticated_client, user, patched_docker_service, fake_container, prepare_servers_data_path):
        game = GameFactory()
        version = GameVersionFactory(game=game)

        url = reverse("server-list")
        data = {
            "name": "My Server",
            "game": game.id,
            "game_version": version.id,
            "description": "Test server",
            "port": 25565,
            "max_players": 20,
            "auto_start": False,
            "auto_update": True,
            "is_public": True,
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data == {
            "id": 1,
            "name": "My Server",
            "game": 1,
            "game_version": 1,
            "description": "Test server",
            "port": 25565,
            "additional_ports": {},
            "max_players": 20,
            "auto_start": False,
            "auto_update": True,
            "backup_enabled": True,
            "is_public": True,
            "configuration": {
                "config_data": {},
                "environment_variables": {},
                "docker_volumes": [],
                "memory_limit": "2g",
                "cpu_limit": 2.0,
                "custom_startup_command": "",
            },
        }

    def test_retrieve_own_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, container_id=fake_container.id)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == server.id

    def test_retrieve_other_user_private_server_forbidden(self, authenticated_client, patched_docker_service, fake_container):
        other_user = UserFactory()
        server = ServerInstanceFactory(owner=other_user, is_public=False, container_id=fake_container.id)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_own_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, name="Old Name", container_id=fake_container.id)

        url = reverse("server-detail", kwargs={"pk": server.id})
        data = {"name": "New Name"}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.name == "New Name"

    def test_update_other_user_server_forbidden(self, authenticated_client, patched_docker_service, fake_container):
        other_user = UserFactory()
        server = ServerInstanceFactory(owner=other_user, container_id=fake_container.id)

        url = reverse("server-detail", kwargs={"pk": server.id})
        data = {"name": "Hacked Name"}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_own_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, container_id=fake_container.id)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        from servers.models import ServerInstance

        assert not ServerInstance.objects.filter(id=server.id).exists()

    def test_update_server_full(
        self, authenticated_client, user, patched_docker_service, fake_container, prepare_servers_data_path
    ):
        game = GameFactory()
        version = GameVersionFactory(game=game)

        url = reverse("server-list")
        data = {
            "name": "My Server",
            "game": game.id,
            "game_version": version.id,
            "description": "Test server",
            "port": 25565,
            "max_players": 20,
        }
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "My Server"
        server = ServerInstance.objects.get(id=response.data["id"])

        url = reverse("server-detail", kwargs={"pk": server.id})
        data = {
            "name": "Updated Name",
            "description": "Updated description",
            "port": 25566,
            "max_players": 30,
            "status": "running",
            "auto_start": True,
            "auto_update": True,
            "backup_enabled": False,
            "is_public": True,
            "configuration": {
                "config_data": {
                    "key": "value",
                },
                "environment_variables": {
                    "key": "value",
                },
                "docker_volumes": {"data": {"source": "/path/to/source", "target": "/path/to/target"}},
                "memory_limit": "2g",
                "cpu_limit": 2.0,
                "custom_startup_command": "echo 'Hello, world!'",
            },
        }

        response = authenticated_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.name == "Updated Name"
        assert server.port == 25566
        assert server.status == "running"
        assert server.auto_start is True
        assert server.auto_update is True
        assert server.backup_enabled is False
        assert server.is_public is True
        assert server.configuration.config_data == {"key": "value"}
        assert server.configuration.environment_variables == {"key": "value"}
        assert server.configuration.docker_volumes == {"data": {"source": "/path/to/source", "target": "/path/to/target"}}
        assert server.configuration.memory_limit == "2g"
        assert server.configuration.cpu_limit == 2.0
        assert server.configuration.custom_startup_command == "echo 'Hello, world!'"

    def test_partial_update_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, name="Old Name", container_id=fake_container.id)

        url = reverse("server-detail", kwargs={"pk": server.id})
        data = {"name": "Partially Updated"}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.name == "Partially Updated"


@pytest.mark.django_db
class TestServerActions:
    def test_start_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.CREATED, container_id=fake_container.id)

        url = reverse("server-start", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.start_server_task.delay", lambda server_id: start_server_task.apply(args=[server_id, user.id])
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.status == ServerInstance.RUNNING

    def test_start_already_running_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.RUNNING, container_id=fake_container.id)

        url = reverse("server-start", kwargs={"pk": server.id})

        with patch("docker_manager.tasks.start_server_task.delay", lambda server_id: start_server_task.apply(args=[server_id])):
            authenticated_client.post(url)
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_stop_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.RUNNING, container_id=fake_container.id)

        url = reverse("server-stop", kwargs={"pk": server.id})
        with patch("docker_manager.tasks.stop_server_task.delay", lambda server_id: stop_server_task.apply(args=[server_id])):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.status == ServerInstance.STOPPED

    def test_stop_already_stopped_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.STOPPED, container_id=fake_container.id)

        url = reverse("server-stop", kwargs={"pk": server.id})
        with patch("docker_manager.tasks.stop_server_task.delay", lambda server_id: stop_server_task.apply(args=[server_id])):
            authenticated_client.post(url)
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_restart_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.RUNNING, container_id=fake_container.id)

        url = reverse("server-restart", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.restart_server_task.delay", lambda server_id: restart_server_task.apply(args=[server_id])
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK

    def test_update_server_stopped(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.CREATED, container_id=fake_container.id)

        first_id = fake_container.id
        url = reverse("server-update-server", kwargs={"pk": server.id})
        with (
            patch(
                "docker_manager.tasks.update_server_task.delay",
                lambda server_id: update_server_task.apply(args=[server_id, user.id]),
            ),
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert first_id != server.container_id
        assert server.status == ServerInstance.STOPPED

    def test_update_running_server_without_force(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.RUNNING, container_id=fake_container.id)

        _server = ServerInstance.objects.first()
        assert _server.status == ServerInstance.RUNNING
        assert _server.id == server.id

        url = reverse("server-update-server", kwargs={"pk": server.id})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_running_server_with_force(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.RUNNING, container_id=fake_container.id)
        first_id = fake_container.id
        url = reverse("server-update-server", kwargs={"pk": server.id})
        with (
            patch("docker_manager.tasks.update_server_task.delay", lambda server_id: update_server_task.apply(args=[server_id])),
        ):
            response = authenticated_client.post(url, data={"force": True}, format="json")

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.status == ServerInstance.STOPPED
        assert first_id != server.container_id
        assert patched_docker_service.containers.get(server.container_id).status == "created"

    def test_get_server_logs(self, authenticated_client, user):
        server = ServerInstanceFactory(owner=user)

        url = reverse("server-logs", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "logs" in response.data
        assert "container_id" in response.data

    def test_get_status_history(self, authenticated_client, user):
        server = ServerInstanceFactory(owner=user)
        from servers.tests.servers_factories import ServerStatusFactory

        ServerStatusFactory.create_batch(5, server=server)

        url = reverse("server-status-history", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 5


@pytest.mark.django_db
class TestServerPlayersManagement:
    def test_list_server_players(self, authenticated_client, user):
        server = ServerInstanceFactory(owner=user)
        ServerPlayerFactory.create_batch(5, server=server)

        url = reverse("server-players", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 5

    def test_add_player(self, authenticated_client, user):
        server = ServerInstanceFactory(owner=user)

        url = reverse("server-players", kwargs={"pk": server.id})
        data = {
            "minecraft_username": "Steve",
            "minecraft_uuid": "12345678-1234-1234-1234-123456789012",
            "permission_level": "player",
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        from servers.models import ServerPlayer

        assert ServerPlayer.objects.filter(server=server, minecraft_username="Steve").exists()


@pytest.mark.django_db
class TestPermissions:
    def test_user_cannot_access_other_user_server(self, authenticated_client, patched_docker_service, fake_container):
        other_user = UserFactory()
        server = ServerInstanceFactory(owner=other_user, is_public=False, container_id=fake_container.id)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_can_access_all_servers(self, admin_client):
        other_user = UserFactory()
        server = ServerInstanceFactory(owner=other_user, is_public=False)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = admin_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_cannot_create_server(self, api_client):
        game = GameFactory()
        version = GameVersionFactory(game=game)

        url = reverse("server-list")
        data = {"name": "Test", "game": game.id, "game_version": version.id, "port": 25565}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestServerPlayerViewSet:
    def test_list_server_players_viewset(self, authenticated_client, user):
        server = ServerInstanceFactory(owner=user)
        ServerPlayerFactory.create_batch(3, server=server)

        url = reverse("serverplayer-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 3

    def test_retrieve_server_player(self, authenticated_client, user):
        server = ServerInstanceFactory(owner=user)
        player = ServerPlayerFactory(server=server, minecraft_username="TestPlayer")

        url = reverse("serverplayer-detail", kwargs={"pk": player.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["minecraft_username"] == "TestPlayer"

    def test_update_server_player(self, authenticated_client, user):
        server = ServerInstanceFactory(owner=user)
        player = ServerPlayerFactory(server=server, permission_level="player")

        url = reverse("serverplayer-detail", kwargs={"pk": player.id})
        data = {"permission_level": "moderator", "is_banned": False}

        response = authenticated_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        player.refresh_from_db()
        assert player.permission_level == "moderator"

    def test_partial_update_server_player(self, authenticated_client, user):
        server = ServerInstanceFactory(owner=user)
        player = ServerPlayerFactory(server=server, is_banned=False)

        url = reverse("serverplayer-detail", kwargs={"pk": player.id})
        data = {"is_banned": True}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        player.refresh_from_db()
        assert player.is_banned is True

    def test_delete_server_player(self, authenticated_client, user):
        server = ServerInstanceFactory(owner=user)
        player = ServerPlayerFactory(server=server)

        url = reverse("serverplayer-detail", kwargs={"pk": player.id})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        from servers.models import ServerPlayer

        assert not ServerPlayer.objects.filter(id=player.id).exists()
