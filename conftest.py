import os
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile
from docker_manager.tests.docker_mockup import DockerClientMockup

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


@pytest.fixture
def docker_client_mockup():
    """
    Returns a docker client mockup
    """
    return DockerClientMockup()


@pytest.fixture(autouse=True)
def patched_docker_service(docker_client_mockup):
    """
    Patches the docker.from_env function to return the mock docker client
    """
    with patch("docker_manager.services.docker_service.docker.from_env", return_value=docker_client_mockup):
        # Also patch the singleton instance
        with patch("docker_manager.services.docker_service._docker_service", None):
            yield docker_client_mockup


@pytest.fixture
def fake_container(docker_client_mockup):
    """
    Creates a fake container using the docker client mockup
    """
    container = docker_client_mockup.containers.create(
        image="test/image:latest",
        name="test_container",
        ports={"25565/tcp": 25565},
        environment={"TEST_VAR": "test_value"},
        volumes={"/host/data": {"bind": "/container/data", "mode": "rw"}},
        mem_limit="2g",
        nano_cpus=2000000000,
    )
    return container
