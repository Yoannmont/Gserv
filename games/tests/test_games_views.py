import pytest
from django.urls import reverse
from rest_framework import status

from games.models import Game, GameMod, GameVersion
from games.tests.games_factories import (
    GameConfigurationFactory,
    GameFactory,
    GameModFactory,
    GameVersionFactory,
)


@pytest.mark.django_db
class TestGameViewSet:
    def test_list_games(self, api_client):
        GameFactory.create_batch(3, is_active=True)
        GameFactory(is_active=False)  # Should not appear

        url = reverse("game-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_retrieve_game(self, api_client):
        game = GameFactory(slug="minecraft")

        url = reverse("game-detail", kwargs={"slug": "minecraft"})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == game.name

    def test_create_game_as_admin(self, admin_client):
        url = reverse("game-list")
        data = {
            "name": "New Game",
            "slug": "new-game",
            "description": "A new game",
            "docker_image": "game/new:latest",
            "default_port": 25565,
        }

        response = admin_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Game"

    def test_create_game_as_user_forbidden(self, authenticated_client):
        url = reverse("game-list")
        data = {
            "name": "New Game",
            "slug": "new-game",
            "description": "A new game",
            "docker_image": "game/new:latest",
            "default_port": 25565,
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_game_versions_action(self, api_client):
        game = GameFactory(slug="minecraft")
        GameVersionFactory.create_batch(3, game=game)

        url = reverse("game-versions", kwargs={"slug": "minecraft"})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3

    def test_game_mods_action(self, api_client):
        game = GameFactory(slug="minecraft")
        GameModFactory.create_batch(5, game=game, is_active=True)
        GameModFactory(game=game, is_active=False)

        url = reverse("game-mods", kwargs={"slug": "minecraft"})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 5

    def test_game_mods_filter_by_version(self, api_client):
        """Test filtering mods by version"""
        game = GameFactory(slug="minecraft")
        v1 = GameVersionFactory(game=game, version="1.19")
        v2 = GameVersionFactory(game=game, version="1.20")

        GameModFactory(game=game, compatible_game_versions=[v1])
        GameModFactory(game=game, compatible_game_versions=[v2])
        GameModFactory(game=game, compatible_game_versions=[v1, v2])

        url = reverse("game-mods", kwargs={"slug": "minecraft"})
        response = api_client.get(url, {"version": "1.19"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2  # mod1 and mod3

    def test_update_game(self, admin_client):
        game = GameFactory(slug="test-game", name="Test Game")
        url = reverse("game-detail", kwargs={"slug": "test-game"})
        data = {
            "name": "Updated Game",
            "description": "Updated description",
            "game_id": game.id,
            "slug": "updated-game",
            "docker_image": "game/updated:latest",
            "default_port": 44444,
            "documentation_url": "https://example.com",
            "is_active": True,
        }

        response = admin_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        game.refresh_from_db()
        assert game.name == "Updated Game"
        assert game.slug == "updated-game"
        assert game.docker_image == "game/updated:latest"
        assert game.default_port == 44444
        assert game.documentation_url == "https://example.com"
        assert game.is_active is True

    def test_partial_update_game(self, admin_client):
        game = GameFactory(
            slug="test-game",
            name="Test Game",
            description="Test Description",
            docker_image="game/test:latest",
            default_port=25565,
            documentation_url="https://example.com",
            is_active=True,
        )
        url = reverse("game-detail", kwargs={"slug": "test-game"})
        data = {
            "description": "New description",
            "game_id": game.id,
            "slug": "updated-game",
            "docker_image": "game/updated:latest",
            "default_port": 44444,
            "documentation_url": "https://example.com",
            "is_active": True,
        }
        response = admin_client.patch(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        game.refresh_from_db()
        assert game.description == "New description"
        assert game.slug == "updated-game"
        assert game.docker_image == "game/updated:latest"
        assert game.default_port == 44444
        assert game.documentation_url == "https://example.com"
        assert game.is_active is True

    def test_delete_game(self, admin_client):
        game = GameFactory(slug="test-game", name="Test Game")
        url = reverse("game-detail", kwargs={"slug": "test-game"})

        response = admin_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Game.objects.filter(id=game.id).exists()

    def test_game_configurations_action(self, api_client):
        """Test retrieving game configurations"""
        game = GameFactory(slug="minecraft")
        GameConfigurationFactory.create_batch(3, game=game)

        url = reverse("game-configurations", kwargs={"slug": "minecraft"})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3


@pytest.mark.django_db
class TestGameVersionViewSet:
    def test_list_versions(self, api_client):
        game = GameFactory()
        GameVersionFactory.create_batch(3, game=game)

        url = reverse("gameversion-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_filter_versions_by_game(self, api_client):
        game1 = GameFactory()
        game2 = GameFactory()

        GameVersionFactory.create_batch(2, game=game1)
        GameVersionFactory.create_batch(3, game=game2)

        url = reverse("gameversion-list")
        response = api_client.get(url, {"game": game1.id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_create_version_as_admin(self, admin_client):
        game = GameFactory()

        url = reverse("gameversion-list")
        data = {
            "game_id": game.id,
            "version": "1.21.0",
            "is_stable": True,
            "is_recommended": True,
            "docker_tag": "latest",
        }

        response = admin_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["version"] == "1.21.0"
        assert response.data["is_stable"] is True
        assert response.data["is_recommended"] is True
        assert response.data["docker_tag"] == "latest"

    def test_retrieve_version(self, api_client):
        """Test retrieving a version"""
        game = GameFactory()
        version = GameVersionFactory(game=game, version="1.20.0")

        url = reverse("gameversion-detail", kwargs={"pk": version.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["version"] == "1.20.0"

    def test_update_version(self, admin_client):
        game = GameFactory()
        version = GameVersionFactory(game=game, version="1.20.0", is_stable=False)

        url = reverse("gameversion-detail", kwargs={"pk": version.id})
        data = {
            "game_id": game.id,
            "version": "1.20.1",
            "is_stable": True,
            "is_recommended": True,
            "docker_tag": "latest",
        }

        response = admin_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        version.refresh_from_db()
        assert version.version == "1.20.1"
        assert version.is_stable is True
        assert version.is_recommended is True
        assert version.docker_tag == "latest"

    def test_delete_version(self, admin_client):
        game = GameFactory()
        version = GameVersionFactory(game=game)

        url = reverse("gameversion-detail", kwargs={"pk": version.id})
        response = admin_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestGameModViewSet:
    def test_list_mods(self, api_client):
        GameModFactory.create_batch(5, is_active=True)
        GameModFactory(is_active=False)  # Should not appear

        url = reverse("gamemod-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 5

    def test_filter_mods_by_type(self, api_client):
        GameModFactory.create_batch(2, mod_type="plugin")
        GameModFactory.create_batch(3, mod_type="mod")

        url = reverse("gamemod-list")
        response = api_client.get(url, {"mod_type": "plugin"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_search_mods(self, api_client):
        GameModFactory(name="OptiFine", is_active=True)
        GameModFactory(name="Sodium", is_active=True)
        GameModFactory(name="Lithium", is_active=True)

        url = reverse("gamemod-list")
        response = api_client.get(url, {"search": "OptiFine"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "OptiFine"

    def test_create_mod_as_admin(self, admin_client):
        game = GameFactory()
        version = GameVersionFactory(game=game)

        url = reverse("gamemod-list")
        data = {
            "game": game.id,
            "name": "New Mod",
            "slug": "new-mod",
            "description": "A new mod",
            "mod_type": "mod",
            "version": "1.0",
            "download_url": "https://example.com/mod.jar",
            "file_name": "new-mod.jar",
            "compatible_game_versions": [version.id],
        }

        response = admin_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_mod(self, api_client):
        """Test retrieving a mod"""
        game = GameFactory()
        mod = GameModFactory(game=game, name="Test Mod")

        url = reverse("gamemod-detail", kwargs={"pk": mod.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Test Mod"

    def test_update_mod(self, admin_client):
        game = GameFactory()
        mod = GameModFactory(game=game, name="Old Name")
        version = GameVersionFactory(game=game, version="1.20")

        assert GameVersion.objects.filter(game=game).exists()
        url = reverse("gamemod-detail", kwargs={"pk": mod.id})
        data = {
            "game": game.id,
            "name": "New Name",
            "slug": "new-mod",
            "description": "Updated description",
            "mod_type": "mod",
            "version": "1.0",
            "download_url": "https://example.com/mod.jar",
            "file_name": "new-mod.jar",
            "compatible_game_versions": [version.id],
            "author": "John Doe",
            "website": "https://example.com",
            "is_active": True,
        }

        response = admin_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        mod.refresh_from_db()
        assert mod.name == "New Name"
        assert mod.description == "Updated description"
        assert mod.mod_type == "mod"
        assert mod.version == "1.0"
        assert mod.download_url == "https://example.com/mod.jar"
        assert mod.file_name == "new-mod.jar"
        assert mod.compatible_game_versions.count() == 1
        assert mod.compatible_game_versions.first().id == version.id
        assert mod.author == "John Doe"
        assert mod.website == "https://example.com"
        assert mod.is_active is True
        assert mod.game == game
        assert mod.slug == "new-mod"

    def test_partial_update_mod(self, admin_client):
        """Test partial update of a mod"""
        game = GameFactory()
        mod = GameModFactory(game=game, name="Test Mod")

        url = reverse("gamemod-detail", kwargs={"pk": mod.id})
        data = {"description": "New description"}

        response = admin_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        mod.refresh_from_db()
        assert mod.description == "New description"

    def test_delete_mod(self, admin_client):
        """Test deleting a mod"""
        game = GameFactory()
        mod = GameModFactory(game=game)

        url = reverse("gamemod-detail", kwargs={"pk": mod.id})
        response = admin_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not GameMod.objects.filter(game=game).exists()


@pytest.mark.django_db
class TestGameConfigurationViewSet:
    def test_list_configurations(self, api_client):
        GameConfigurationFactory.create_batch(3)

        url = reverse("gameconfiguration-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_filter_configurations_by_game(self, api_client):
        game1 = GameFactory()
        game2 = GameFactory()

        GameConfigurationFactory.create_batch(2, game=game1)
        GameConfigurationFactory(game=game2)

        url = reverse("gameconfiguration-list")
        response = api_client.get(url, {"game": game1.id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_retrieve_configuration(self, api_client):
        """Test retrieving a configuration"""
        game = GameFactory()
        config = GameConfigurationFactory(game=game, name="Test Config")

        url = reverse("gameconfiguration-detail", kwargs={"pk": config.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Test Config"

    def test_create_configuration_as_admin(self, admin_client):
        """Test creating a configuration"""
        game = GameFactory()

        url = reverse("gameconfiguration-list")
        data = {
            "game": game.id,
            "name": "New Config",
            "config_data": {"key": "value"},
            "is_default": False,
        }

        response = admin_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Config"

    def test_update_configuration(self, admin_client):
        game = GameFactory()
        config = GameConfigurationFactory(game=game, name="Old Name")

        url = reverse("gameconfiguration-detail", kwargs={"pk": config.id})
        data = {"game": game.id, "name": "Updated Name", "config_data": {"new_key": "new_value"}}

        response = admin_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        config.refresh_from_db()
        assert config.name == "Updated Name"
        assert config.config_data == {"new_key": "new_value"}
        assert config.game == game
        assert config.is_default is False

    def test_partial_update_configuration(self, admin_client):
        """Test partial update of a configuration"""
        game = GameFactory()
        config = GameConfigurationFactory(game=game, is_default=False)

        url = reverse("gameconfiguration-detail", kwargs={"pk": config.id})
        data = {"is_default": True}

        response = admin_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        config.refresh_from_db()
        assert config.is_default is True

    def test_delete_configuration(self, admin_client):
        """Test deleting a configuration"""
        game = GameFactory()
        config = GameConfigurationFactory(game=game)

        url = reverse("gameconfiguration-detail", kwargs={"pk": config.id})
        response = admin_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
