import pytest
from django.urls import reverse
from rest_framework import status

from accounts.tests.accounts_factories import UserFactory
from games.tests.games_factories import GameFactory, GameModFactory, GameVersionFactory
from servers.models import ServerInstance
from servers.tests.servers_factories import (
    ServerInstanceFactory,
    ServerModFactory,
    ServerPlayerFactory,
)


@pytest.mark.django_db
class TestServerInstanceViewSet:
    def test_list_servers_as_owner(self, authenticated_client, user):
        """Test liste des serveurs par le propriétaire"""
        ServerInstanceFactory.create_batch(3, owner=user)
        ServerInstanceFactory()  # Serveur d'un autre user

        url = reverse("server-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_list_public_servers(self, authenticated_client, user):
        """Test que les serveurs publics sont visibles"""
        ServerInstanceFactory.create_batch(2, owner=user)
        ServerInstanceFactory(is_public=True)  # Serveur public d'un autre user
        ServerInstanceFactory(is_public=False)  # Serveur privé invisible

        url = reverse("server-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_list_servers_as_admin(self, admin_client):
        """Test que les admins voient tous les serveurs"""
        ServerInstanceFactory.create_batch(5)

        url = reverse("server-list")
        response = admin_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 5

    def test_create_server(self, authenticated_client, user):
        """Test création d'un serveur"""
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
        assert response.data["name"] == "My Server"

    def test_retrieve_own_server(self, authenticated_client, user):
        """Test détail de son propre serveur"""
        server = ServerInstanceFactory(owner=user)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == server.id

    def test_retrieve_other_user_private_server_forbidden(self, authenticated_client):
        """Test qu'on ne peut pas voir le serveur privé d'un autre user"""
        other_user = UserFactory()
        server = ServerInstanceFactory(owner=other_user, is_public=False)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_own_server(self, authenticated_client, user):
        """Test mise à jour de son serveur"""
        server = ServerInstanceFactory(owner=user, name="Old Name")

        url = reverse("server-detail", kwargs={"pk": server.id})
        data = {"name": "New Name"}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.name == "New Name"

    def test_update_other_user_server_forbidden(self, authenticated_client):
        """Test qu'on ne peut pas modifier le serveur d'un autre user"""
        other_user = UserFactory()
        server = ServerInstanceFactory(owner=other_user)

        url = reverse("server-detail", kwargs={"pk": server.id})
        data = {"name": "Hacked Name"}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_own_server(self, authenticated_client, user):
        """Test suppression de son serveur"""
        server = ServerInstanceFactory(owner=user)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        from servers.models import ServerInstance

        assert not ServerInstance.objects.filter(id=server.id).exists()


@pytest.mark.django_db
class TestServerActions:
    def test_start_server(self, authenticated_client, user):
        """Test démarrage d'un serveur"""
        server = ServerInstanceFactory(owner=user, status="stopped")

        url = reverse("server-start", kwargs={"pk": server.id})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.status == "starting"

    def test_start_already_running_server(self, authenticated_client, user):
        """Test erreur si serveur déjà démarré"""
        server = ServerInstanceFactory(owner=user, status="running")

        url = reverse("server-start", kwargs={"pk": server.id})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_stop_server(self, authenticated_client, user):
        """Test arrêt d'un serveur"""
        server = ServerInstanceFactory(owner=user, status="running")

        url = reverse("server-stop", kwargs={"pk": server.id})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.status == "stopping"

    def test_restart_server(self, authenticated_client, user):
        """Test redémarrage d'un serveur"""
        server = ServerInstanceFactory(owner=user, status="running")

        url = reverse("server-restart", kwargs={"pk": server.id})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK

    def test_update_server_stopped(self, authenticated_client, user):
        """Test mise à jour d'un serveur arrêté"""
        server = ServerInstanceFactory(owner=user, status="stopped")

        url = reverse("server-update-server", kwargs={"pk": server.id})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        server.refresh_from_db()
        assert server.status == "updating"

    def test_update_running_server_without_force(self, authenticated_client, user):
        """Test erreur de mise à jour sans force sur serveur en cours"""
        server = ServerInstanceFactory(owner=user, status="running")

        _server = ServerInstance.objects.first()
        assert _server.status == "running"
        assert _server.id == server.id

        url = reverse("server-update-server", kwargs={"pk": server.id})
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_status_history(self, authenticated_client, user):
        """Test récupération de l'historique des statuts"""
        server = ServerInstanceFactory(owner=user)
        from servers.tests.servers_factories import ServerStatusFactory

        ServerStatusFactory.create_batch(5, server=server)

        url = reverse("server-status-history", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 5


@pytest.mark.django_db
class TestServerModsManagement:
    def test_list_server_mods(self, authenticated_client, user):
        """Test liste des mods d'un serveur"""
        server = ServerInstanceFactory(owner=user)
        ServerModFactory.create_batch(3, server=server)

        url = reverse("server-mods", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3

    def test_install_mod(self, authenticated_client, user):
        """Test installation d'un mod"""
        game = GameFactory()
        server = ServerInstanceFactory(owner=user, game=game)
        mod = GameModFactory(game=game)

        url = reverse("server-mods", kwargs={"pk": int(server.id)})
        data = {"mod_id": mod.id, "is_enabled": True}

        response = authenticated_client.post(url, data=data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        from servers.models import ServerMod

        assert ServerMod.objects.filter(server=server, mod=mod).exists()


@pytest.mark.django_db
class TestServerPlayersManagement:
    def test_list_server_players(self, authenticated_client, user):
        """Test liste des joueurs d'un serveur"""
        server = ServerInstanceFactory(owner=user)
        ServerPlayerFactory.create_batch(5, server=server)

        url = reverse("server-players", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 5

    def test_add_player(self, authenticated_client, user):
        """Test ajout d'un joueur"""
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
    def test_user_cannot_access_other_user_server(self, authenticated_client):
        """Test qu'un user ne peut pas accéder au serveur d'un autre"""
        other_user = UserFactory()
        server = ServerInstanceFactory(owner=other_user, is_public=False)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_can_access_all_servers(self, admin_client):
        """Test que l'admin peut accéder à tous les serveurs"""
        other_user = UserFactory()
        server = ServerInstanceFactory(owner=other_user, is_public=False)

        url = reverse("server-detail", kwargs={"pk": server.id})
        response = admin_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_cannot_create_server(self, api_client):
        """Test qu'un non-authentifié ne peut pas créer de serveur"""
        game = GameFactory()
        version = GameVersionFactory(game=game)

        url = reverse("server-list")
        data = {"name": "Test", "game": game.id, "game_version": version.id, "port": 25565}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
