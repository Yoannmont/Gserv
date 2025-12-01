import pytest
from django.urls import reverse
from rest_framework import status

from accounts.models import User, UserProfile
from accounts.tests.accounts_factories import UserFactory


@pytest.mark.django_db
class TestUserRegistration:
    def test_register_success(self, api_client):
        """Test inscription réussie"""
        url = reverse("user-list")
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "securepass123",
            "password_confirm": "securepass123",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert "user" in response.data
        assert "tokens" in response.data
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]

        assert User.objects.filter(username="newuser").exists()
        user = User.objects.get(username="newuser")
        assert UserProfile.objects.filter(user=user).exists()

    def test_register_password_mismatch(self, api_client):
        """Test erreur si mots de passe différents"""
        url = reverse("user-list")
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "securepass123",
            "password_confirm": "differentpass",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_username(self, api_client):
        """Test erreur si username existe déjà"""
        UserFactory(username="existinguser")

        url = reverse("user-list")
        data = {
            "username": "existinguser",
            "email": "new@example.com",
            "password": "securepass123",
            "password_confirm": "securepass123",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserLogin:
    def test_login_success(self, api_client):
        """Test connexion réussie"""
        UserFactory(username="testuser", password="testpass123")

        url = reverse("token_obtain_pair")
        data = {"username": "testuser", "password": "testpass123"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert "user" in response.data

    def test_login_invalid_credentials(self, api_client):
        """Test connexion avec mauvais identifiants"""
        UserFactory(username="testuser", password="testpass123")

        url = reverse("token_obtain_pair")
        data = {"username": "testuser", "password": "wrongpass"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_inactive_user(self, api_client):
        """Test connexion avec compte inactif"""
        user = UserFactory(username="testuser", password="testpass123")
        user.is_active = False
        user.save()

        url = reverse("token_obtain_pair")
        data = {"username": "testuser", "password": "testpass123"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserProfile:
    def test_get_me_authenticated(self, authenticated_client, user):
        """Test récupération du profil utilisateur connecté"""
        url = reverse("user-me")

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == user.username
        assert response.data["email"] == user.email

    def test_get_me_unauthenticated(self, api_client):
        """Test erreur si non authentifié"""
        url = reverse("user-me")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPasswordChange:
    def test_change_password_success(self, authenticated_client, user):
        """Test changement de mot de passe réussi"""
        url = reverse("user-change-password")
        data = {
            "old_password": "testpass123",
            "new_password": "newpass123",
            "new_password_confirm": "newpass123",
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "tokens" in response.data

        user.refresh_from_db()
        assert user.check_password("newpass123")

    def test_change_password_wrong_old_password(self, authenticated_client, user):
        """Test erreur si ancien mot de passe incorrect"""
        url = reverse("user-change-password")
        data = {
            "old_password": "wrongpass",
            "new_password": "newpass123",
            "new_password_confirm": "newpass123",
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserLogout:
    def test_logout_success(self, authenticated_client):
        """Test déconnexion réussie"""
        from rest_framework_simplejwt.tokens import RefreshToken

        user = UserFactory()
        refresh = RefreshToken.for_user(user)

        url = reverse("token_logout")
        data = {"refresh": str(refresh)}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data

    def test_logout_invalid_token(self, authenticated_client, user):
        """Test déconnexion avec token invalide"""
        url = reverse("token_logout")
        data = {"refresh": "invalid_token"}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    def test_logout_without_token(self, authenticated_client):
        """Test déconnexion sans token"""
        url = reverse("token_logout")
        data = {}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestUserCRUD:
    def test_list_users(self, authenticated_client):
        """Test liste des utilisateurs"""
        UserFactory.create_batch(3)

        url = reverse("user-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 3  # 3 + conftest user

    def test_retrieve_user(self, authenticated_client, user):
        """Test récupération d'un utilisateur"""
        url = reverse("user-detail", kwargs={"pk": user.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == user.id
        assert response.data["username"] == user.username

    def test_update_user(self, authenticated_client, user):
        """Test mise à jour complète d'un utilisateur"""
        url = reverse("user-detail", kwargs={"pk": user.id})
        data = {
            "first_name": "Updated",
            "last_name": "Name",
            "email": "updated@example.com",
            "profile": {
                "bio": "This is a bio",
                "discord_username": "Discord_444",
                "notifications_enabled": False,
                "theme": "light",
            },
        }

        response = authenticated_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.first_name == "Updated"
        assert user.profile.bio == "This is a bio"
        assert user.last_name == "Name"
        assert user.email == "updated@example.com"
        assert user.profile.discord_username == "Discord_444"
        assert user.profile.notifications_enabled is False
        assert user.profile.theme == "light"

    def test_partial_update_user(self, authenticated_client, user):
        """Test mise à jour partielle d'un utilisateur"""
        url = reverse("user-detail", kwargs={"pk": user.id})
        data = {"first_name": "PartiallyUpdated", "profile": {"bio": "OKOK"}}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.first_name == "PartiallyUpdated"
        assert user.profile.bio == "OKOK"

    def test_delete_user(self, authenticated_client, user):
        """Test suppression d'un utilisateur"""
        user_id = user.id
        url = reverse("user-detail", kwargs={"pk": user_id})

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not User.objects.filter(id=user_id).exists()


@pytest.mark.django_db
class TestUserLoginAction:
    def test_login_action_success(self, api_client, user):
        url = reverse("token_obtain_pair")
        data = {"username": user.username, "password": "testpass123"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert "user" in response.data

    def test_login_action_invalid_credentials(self, api_client, user):
        """Test action login avec mauvais identifiants"""
        url = reverse("token_obtain_pair")
        data = {"username": user.username, "password": "wrongpass"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTokenRefresh:
    def test_refresh_token_success(self, api_client, user):
        url = reverse("token_obtain_pair")
        data = {"username": user.username, "password": "testpass123"}
        response = api_client.post(url, data, format="json")
        refresh = response.data["refresh"]

        url = reverse("token_refresh")
        data = {"refresh": str(refresh)}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_refresh_token_invalid(self, api_client):
        url = reverse("token_refresh")
        data = {"refresh": "invalid_token"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
