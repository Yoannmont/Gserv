import os

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile

os.environ.setdefault("DJANGO_CONFIGURATION", "Test")


@pytest.fixture
def api_client():
    """Base API client"""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    """Authenticated API client with a normal user"""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Authenticated API client with an admin"""
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def user(django_user_model):
    """Normal user"""
    user = django_user_model.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123", role="user"
    )

    UserProfile.objects.create(user=user)
    return user


@pytest.fixture
def admin_user(django_user_model):
    """Admin user"""
    user = django_user_model.objects.create_user(
        username="admin", email="admin@example.com", password="adminpass123", role="admin"
    )
    UserProfile.objects.create(user=user)
    return user


@pytest.fixture
def other_user(django_user_model):
    """Other user for permission tests"""
    user = django_user_model.objects.create_user(
        username="otheruser", email="other@example.com", password="otherpass123", role="user"
    )
    UserProfile.objects.create(user=user)
    return user
