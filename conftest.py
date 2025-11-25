import os

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

os.environ.setdefault("DJANGO_CONFIGURATION", "Test")


@pytest.fixture
def api_client():
    """Client API de base"""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    """Client API authentifié avec un utilisateur normal"""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Client API authentifié avec un admin"""
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def user(django_user_model):
    """Utilisateur normal"""
    return django_user_model.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123", role="user"
    )


@pytest.fixture
def admin_user(django_user_model):
    """Utilisateur admin"""
    return django_user_model.objects.create_user(
        username="admin", email="admin@example.com", password="adminpass123", role="admin"
    )


@pytest.fixture
def other_user(django_user_model):
    """Autre utilisateur pour les tests de permissions"""
    return django_user_model.objects.create_user(
        username="otheruser", email="other@example.com", password="otherpass123", role="user"
    )
