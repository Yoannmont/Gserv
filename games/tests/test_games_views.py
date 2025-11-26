import pytest
from django.urls import reverse
from rest_framework import status

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
        GameFactory(is_active=False)  # Ne doit pas apparaître

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
        """Test filtrage des mods par version"""
        game = GameFactory(slug="minecraft")
        v1 = GameVersionFactory(game=game, version="1.19")
        v2 = GameVersionFactory(game=game, version="1.20")

        GameModFactory(game=game, compatible_game_versions=[v1])
        GameModFactory(game=game, compatible_game_versions=[v2])
        GameModFactory(game=game, compatible_game_versions=[v1, v2])

        url = reverse("game-mods", kwargs={"slug": "minecraft"})
        response = api_client.get(url, {"version": "1.19"})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2  # mod1 et mod3


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
        data = {"game_id": game.id, "version": "1.21.0", "is_stable": True, "is_recommended": True}

        response = admin_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestGameModViewSet:
    def test_list_mods(self, api_client):
        GameModFactory.create_batch(5, is_active=True)
        GameModFactory(is_active=False)  # Ne doit pas apparaître

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
