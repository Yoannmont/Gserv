import logging

from django.contrib.auth import logout
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from accounts.serializers import (
    PasswordChangeSerializer,
    TokenObtainSerializer,
    TokenRefreshSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

logger = logging.getLogger(__name__)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Vue personnalisée pour l'obtention de tokens JWT"""

    serializer_class = TokenObtainSerializer

    def post(self, request, *args, **kwargs):
        """Log token obtain request"""
        logger.info("[accounts_token_obtain] Token obtain request")
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            logger.info("[accounts_token_obtain] Token obtained successfully")
        return response


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """Inscription d'un nouvel utilisateur"""
        logger.info("[accounts_user_create] User registration request")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Générer les tokens JWT
        refresh = RefreshToken.for_user(user)
        logger.info(f"[accounts_user_create] User created successfully id={user.id} email={user.email}")

        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )

    def list(self, request, *args, **kwargs):
        """List users"""
        logger.info("[accounts_user_list] User list request")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get user details"""
        user_id = kwargs.get('pk')
        logger.info(f"[accounts_user_retrieve] User retrieve request id={user_id}")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update user"""
        user_id = kwargs.get('pk')
        logger.info(f"[accounts_user_update] User update request id={user_id}")
        response = super().update(request, *args, **kwargs)
        logger.info(f"[accounts_user_update] User updated successfully id={user_id}")
        return response

    def partial_update(self, request, *args, **kwargs):
        """Partial update user"""
        user_id = kwargs.get('pk')
        logger.info(f"[accounts_user_partial_update] User partial update request id={user_id}")
        response = super().partial_update(request, *args, **kwargs)
        logger.info(f"[accounts_user_partial_update] User partially updated successfully id={user_id}")
        return response

    def destroy(self, request, *args, **kwargs):
        """Delete user"""
        user_id = kwargs.get('pk')
        logger.info(f"[accounts_user_destroy] User delete request id={user_id}")
        response = super().destroy(request, *args, **kwargs)
        logger.info(f"[accounts_user_destroy] User deleted successfully id={user_id}")
        return response

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Récupérer les informations de l'utilisateur connecté"""
        logger.info(f"[accounts_user_me] Get current user info id={request.user.id}")
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def login(self, request):
        """Connexion de l'utilisateur et obtention des tokens JWT"""
        username = request.data.get('username', 'unknown')
        logger.info(f"[accounts_user_login] User login request username={username}")
        serializer = TokenObtainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data.get('user', {}).get('id') if isinstance(serializer.validated_data.get('user'), dict) else None
        logger.info(f"[accounts_user_login] User logged in successfully username={username} id={user_id}")
        return Response(serializer.validated_data)

    @action(detail=False, methods=["post"])
    def logout(self, request):
        """Déconnexion de l'utilisateur (blacklist du refresh token)"""
        user_id = request.user.id if request.user.is_authenticated else None
        logger.info(f"[accounts_user_logout] User logout request id={user_id}")
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            logout(request)
            logger.info(f"[accounts_user_logout] User logged out successfully id={user_id}")
            return Response({"message": "Déconnexion réussie"}, status=status.HTTP_200_OK)
        except TokenError:
            logger.warning(f"[accounts_user_logout] Invalid token id={user_id}")
            return Response({"error": "Token invalide"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"[accounts_user_logout] Logout error id={user_id} error={str(e)}")
            return Response(
                {"error": f"Erreur lors de la déconnexion; {e}"}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["post"])
    def refresh(self, request):
        """Rafraîchir le token d'accès"""
        logger.info("[accounts_token_refresh] Token refresh request")
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logger.info("[accounts_token_refresh] Token refreshed successfully")
        return Response(serializer.validated_data)

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        """Changer le mot de passe de l'utilisateur"""
        user_id = request.user.id
        logger.info(f"[accounts_user_change_password] Password change request id={user_id}")
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        # Générer de nouveaux tokens
        refresh = RefreshToken.for_user(user)
        logger.info(f"[accounts_user_change_password] Password changed successfully id={user_id}")

        return Response({
            "message": "Mot de passe modifié avec succès",
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
        })

    @action(detail=False, methods=["patch"])
    def update_profile(self, request):
        """Mettre à jour le profil de l'utilisateur"""
        user_id = request.user.id
        logger.info(f"[accounts_user_update_profile] Profile update request id={user_id}")
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f"[accounts_user_update_profile] Profile updated successfully id={user_id}")

        return Response(UserSerializer(request.user).data)
