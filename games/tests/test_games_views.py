import pytest
from django.urls import reverse
from rest_framework import status

from games.models import Game
from games.tests.games_factories import (
    GameFactory,
)


@pytest.mark.django_db
class TestGameViewSet:
    def test_list_games(self, authenticated_client):
        GameFactory.create_batch(3, is_active=True)
        GameFactory(is_active=False)  # Should not appear

        url = reverse("game-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_retrieve_game(self, authenticated_client):
        game = GameFactory(slug="minecraft")

        url = reverse("game-detail", kwargs={"slug": "minecraft"})
        response = authenticated_client.get(url)

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
