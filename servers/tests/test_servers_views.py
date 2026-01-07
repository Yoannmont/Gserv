from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from accounts.tests.accounts_factories import UserFactory
from games.tests.games_factories import GameFactory, GameVersionFactory
from servers.models import ServerInstance, ServerRole
from servers.tests.servers_factories import (
    ServerInstanceFactory,
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

    def test_create_server(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
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
                "environment_variables": {},
                "docker_volumes": {},
                "memory_limit": "2g",
                "cpu_limit": 2.0,
                "custom_startup_command": "",
                "backup_paths": [],
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

    def test_update_other_user_server_forbidden(self, authenticated_client, user, patched_docker_service, fake_container):
        other_user = UserFactory()
        server = ServerInstanceFactory(owner=other_user, container_id=fake_container.id)
        server.save()

        server.roles.create(user=user, role=ServerRole.ROLE_VIEWER)
        server.save()

        url = reverse("server-detail", kwargs={"pk": server.id})
        data = {"name": "Hacked Name"}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_own_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, container_id=fake_container.id)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        from servers.models import ServerInstance

        assert not ServerInstance.objects.filter(id=server.id).exists()

    def test_update_server_full(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
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
            "auto_start": True,
            "auto_update": True,
            "backup_enabled": False,
            "is_public": True,
            "configuration": {
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
        assert server.auto_start is True
        assert server.auto_update is True
        assert server.backup_enabled is False
        assert server.is_public is True
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
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK

    def test_start_already_running_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.RUNNING, container_id=fake_container.id)

        url = reverse("server-start", kwargs={"pk": server.id})

        with patch(
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            authenticated_client.post(url)
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_stop_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.RUNNING, container_id=fake_container.id)

        url = reverse("server-stop", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.stop_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK

    def test_stop_already_stopped_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.STOPPED, container_id=fake_container.id)

        url = reverse("server-stop", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.stop_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            authenticated_client.post(url)
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_restart_server(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.RUNNING, container_id=fake_container.id)

        url = reverse("server-restart", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.restart_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK

    def test_update_server_stopped(self, authenticated_client, user, patched_docker_service, fake_container):
        server = ServerInstanceFactory(owner=user, status=ServerInstance.CREATED, container_id=fake_container.id)

        url = reverse("server-update-server", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.update_server_task",
            lambda server_id: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK

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
        with patch(
            "docker_manager.tasks.update_server_task",
            lambda server_id: None,
        ):
            response = authenticated_client.post(url, data={"force": True}, format="json")

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.status == ServerInstance.STOPPED
        assert first_id != server.container_id
        assert patched_docker_service.containers.get(server.container_id).status == "created"

    def test_get_status_history(self, authenticated_client, user):
        server = ServerInstanceFactory(owner=user)
        from servers.tests.servers_factories import ServerStatusFactory

        ServerStatusFactory.create_batch(5, server=server)

        url = reverse("server-status-history", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 5


@pytest.mark.django_db
class TestPortValidation:
    def test_create_server_with_used_port_running(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
    ):
        game = GameFactory()
        version = GameVersionFactory(game=game)
        existing_server = ServerInstanceFactory(
            owner=user,
            port=25565,
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )

        url = reverse("server-list")
        data = {
            "name": "New Server",
            "game": game.id,
            "game_version": version.id,
            "port": 25565,
            "max_players": 20,
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "port" in response.data["details"]
        assert str(existing_server.id) in response.data["details"]["port"][0]

    def test_create_server_with_used_port_starting(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
    ):
        game = GameFactory()
        version = GameVersionFactory(game=game)
        ServerInstanceFactory(
            owner=user,
            port=25566,
            status=ServerInstance.STARTING,
            container_id=fake_container.id,
        )

        url = reverse("server-list")
        data = {
            "name": "New Server",
            "game": game.id,
            "game_version": version.id,
            "port": 25566,
            "max_players": 20,
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "port" in response.data["details"]

    def test_create_server_with_used_port_creating(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
    ):
        game = GameFactory()
        version = GameVersionFactory(game=game)
        ServerInstanceFactory(
            owner=user,
            port=25567,
            status=ServerInstance.CREATING,
            container_id=fake_container.id,
        )

        url = reverse("server-list")
        data = {
            "name": "New Server",
            "game": game.id,
            "game_version": version.id,
            "port": 25567,
            "max_players": 20,
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "port" in response.data["details"]

    def test_create_server_with_used_additional_port(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
    ):
        game = GameFactory()
        version = GameVersionFactory(game=game)
        ServerInstanceFactory(
            owner=user,
            port=25568,
            additional_ports={"27015": 27016},
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )

        url = reverse("server-list")
        data = {
            "name": "New Server",
            "game": game.id,
            "game_version": version.id,
            "port": 25569,
            "additional_ports": {"27015": 27016},
            "max_players": 20,
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "port" in response.data["details"]

    def test_create_server_with_port_used_as_additional(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
    ):
        game = GameFactory()
        version = GameVersionFactory(game=game)
        ServerInstanceFactory(
            owner=user,
            port=25570,
            additional_ports={"27015": 27017},
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )

        url = reverse("server-list")
        data = {
            "name": "New Server",
            "game": game.id,
            "game_version": version.id,
            "port": 27017,
            "max_players": 20,
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "port" in response.data["details"]

    def test_create_server_with_stopped_port_allowed(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
    ):
        game = GameFactory()
        version = GameVersionFactory(game=game)
        ServerInstanceFactory(owner=user, port=25571, status=ServerInstance.STOPPED)

        url = reverse("server-list")
        data = {
            "name": "New Server",
            "game": game.id,
            "game_version": version.id,
            "port": 25571,
            "max_players": 20,
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_start_server_with_used_port(self, authenticated_client, user, patched_docker_service, fake_container):
        existing_server = ServerInstanceFactory(
            owner=user,
            port=25572,
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        server = ServerInstanceFactory(owner=user, port=25572, status=ServerInstance.CREATED)

        url = reverse("server-start", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "port" in response.data["error"]
        assert str(existing_server.id) in response.data["error"]

    def test_start_server_with_used_additional_port(self, authenticated_client, user, patched_docker_service, fake_container):
        ServerInstanceFactory(
            owner=user,
            port=25573,
            additional_ports={"27015": 27018},
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        server = ServerInstanceFactory(
            owner=user,
            port=25574,
            additional_ports={"27015": 27018},
            status=ServerInstance.CREATED,
        )

        url = reverse("server-start", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "port" in response.data["error"]

    def test_start_server_with_port_used_as_additional(self, authenticated_client, user, patched_docker_service, fake_container):
        ServerInstanceFactory(
            owner=user,
            port=25575,
            additional_ports={"27015": 27019},
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        server = ServerInstanceFactory(owner=user, port=27019, status=ServerInstance.CREATED)

        url = reverse("server-start", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "port" in response.data["error"]

    def test_start_server_with_stopped_port_allowed(self, authenticated_client, user, patched_docker_service, fake_container):
        ServerInstanceFactory(owner=user, port=25576, status=ServerInstance.STOPPED)
        server = ServerInstanceFactory(
            owner=user,
            port=25576,
            status=ServerInstance.CREATED,
            container_id=fake_container.id,
        )

        url = reverse("server-start", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK

    def test_start_server_with_container_id_but_stopped(self, authenticated_client, user, patched_docker_service, fake_container):
        ServerInstanceFactory(
            owner=user,
            port=25577,
            status=ServerInstance.STOPPED,
            container_id=fake_container.id,
        )
        server = ServerInstanceFactory(owner=user, port=25577, status=ServerInstance.CREATED)

        url = reverse("server-start", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "port" in response.data["error"]


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
        data = {
            "name": "Test",
            "game": game.id,
            "game_version": version.id,
            "port": 25565,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestResourceValidation:
    def test_create_server_exceeds_memory_limit(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
        settings,
    ):
        settings.MAX_MEMORY_GLOBAL = "4g"
        game = GameFactory()
        version = GameVersionFactory(game=game)
        other_user = UserFactory()
        ServerInstanceFactory(
            owner=other_user,
            port=30000,
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        from servers.tests.servers_factories import ServerConfigurationFactory

        ServerConfigurationFactory(server=ServerInstance.objects.first(), memory_limit="3g")

        url = reverse("server-list")
        data = {
            "name": "New Server",
            "game": game.id,
            "game_version": version.id,
            "port": 30001,
            "configuration": {"memory_limit": "2g", "cpu_limit": 2.0},
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "resources" in response.data["details"]
        assert "mémoire" in response.data["details"]["resources"][0].lower()

    def test_create_server_exceeds_cpu_limit(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
        settings,
    ):
        settings.MAX_CPU_GLOBAL = 4.0
        game = GameFactory()
        version = GameVersionFactory(game=game)
        other_user = UserFactory()
        ServerInstanceFactory(
            owner=other_user,
            port=30002,
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        from servers.tests.servers_factories import ServerConfigurationFactory

        ServerConfigurationFactory(server=ServerInstance.objects.first(), cpu_limit=3.0)

        url = reverse("server-list")
        data = {
            "name": "New Server",
            "game": game.id,
            "game_version": version.id,
            "port": 30003,
            "configuration": {"memory_limit": "2g", "cpu_limit": 2.0},
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "resources" in response.data["details"]
        assert "cpu" in response.data["details"]["resources"][0].lower()

    def test_create_server_with_force_bypasses_limit(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
        settings,
    ):
        settings.MAX_MEMORY_GLOBAL = "4g"
        game = GameFactory()
        version = GameVersionFactory(game=game)
        other_user = UserFactory()
        ServerInstanceFactory(
            owner=other_user,
            port=30004,
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        from servers.tests.servers_factories import ServerConfigurationFactory

        ServerConfigurationFactory(server=ServerInstance.objects.first(), memory_limit="3g")

        url = reverse("server-list")
        data = {
            "name": "New Server",
            "game": game.id,
            "game_version": version.id,
            "port": 30005,
            "configuration": {"memory_limit": "2g", "cpu_limit": 2.0},
            "force": True,
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_start_server_exceeds_memory_limit(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        settings,
    ):
        settings.MAX_MEMORY_GLOBAL = "4g"
        other_user = UserFactory()
        ServerInstanceFactory(
            owner=other_user,
            port=30006,
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        from servers.tests.servers_factories import ServerConfigurationFactory

        ServerConfigurationFactory(server=ServerInstance.objects.first(), memory_limit="3g")
        server = ServerInstanceFactory(owner=user, port=30007, status=ServerInstance.CREATED)
        ServerConfigurationFactory(server=server, memory_limit="2g")

        url = reverse("server-start", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "mémoire" in response.data["error"].lower()

    def test_start_server_exceeds_cpu_limit(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        settings,
    ):
        settings.MAX_CPU_GLOBAL = 4.0
        other_user = UserFactory()
        ServerInstanceFactory(
            owner=other_user,
            port=30008,
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        from servers.tests.servers_factories import ServerConfigurationFactory

        ServerConfigurationFactory(server=ServerInstance.objects.first(), cpu_limit=3.0)
        server = ServerInstanceFactory(owner=user, port=30009, status=ServerInstance.CREATED)
        ServerConfigurationFactory(server=server, cpu_limit=2.0)

        url = reverse("server-start", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "cpu" in response.data["error"].lower()

    def test_start_server_with_force_bypasses_limit(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        settings,
    ):
        settings.MAX_MEMORY_GLOBAL = "4g"
        other_user = UserFactory()
        ServerInstanceFactory(
            owner=other_user,
            port=30010,
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        from servers.tests.servers_factories import ServerConfigurationFactory

        ServerConfigurationFactory(server=ServerInstance.objects.first(), memory_limit="3g")
        server = ServerInstanceFactory(
            owner=user,
            port=30011,
            status=ServerInstance.CREATED,
            container_id=fake_container.id,
        )
        ServerConfigurationFactory(server=server, memory_limit="2g")

        url = reverse("server-start", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url, data={"force": True}, format="json")

        assert response.status_code == status.HTTP_200_OK

    def test_create_server_within_limits_allowed(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        prepare_servers_data_path,
        settings,
    ):
        settings.MAX_MEMORY_GLOBAL = "8g"
        settings.MAX_CPU_GLOBAL = 8.0
        game = GameFactory()
        version = GameVersionFactory(game=game)
        ServerInstanceFactory(
            owner=user,
            port=30012,
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        from servers.tests.servers_factories import ServerConfigurationFactory

        ServerConfigurationFactory(server=ServerInstance.objects.first(), memory_limit="2g", cpu_limit=2.0)

        url = reverse("server-list")
        data = {
            "name": "New Server",
            "game": game.id,
            "game_version": version.id,
            "port": 30013,
            "configuration": {"memory_limit": "2g", "cpu_limit": 2.0},
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_start_server_within_limits_allowed(
        self,
        authenticated_client,
        user,
        patched_docker_service,
        fake_container,
        settings,
    ):
        settings.MAX_MEMORY_GLOBAL = "8g"
        settings.MAX_CPU_GLOBAL = 8.0
        ServerInstanceFactory(
            owner=user,
            port=30014,
            status=ServerInstance.RUNNING,
            container_id=fake_container.id,
        )
        from servers.tests.servers_factories import ServerConfigurationFactory

        ServerConfigurationFactory(server=ServerInstance.objects.first(), memory_limit="2g", cpu_limit=2.0)
        server = ServerInstanceFactory(
            owner=user,
            port=30015,
            status=ServerInstance.CREATED,
            container_id=fake_container.id,
        )
        ServerConfigurationFactory(server=server, memory_limit="2g", cpu_limit=2.0)

        url = reverse("server-start", kwargs={"pk": server.id})
        with patch(
            "docker_manager.tasks.start_server_task.delay",
            lambda server_id, user_id=None: None,
        ):
            response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
