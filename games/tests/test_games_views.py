import pytest
from django.urls import reverse
from rest_framework import status

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
