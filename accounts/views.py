import logging

from django.contrib.auth import logout
from django.db import IntegrityError, transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from accounts.serializers import (
    PasswordChangeSerializer,
    TokenObtainSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

logger = logging.getLogger(__name__)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = TokenObtainSerializer
    throttle_classes = []

    def post(self, request, *args, **kwargs):
        username = request.data.get("username", "unknown")
        logger.info(f"[accounts_token_obtain] Token obtain request username={username}")
        try:
            serializer = self.get_serializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            logger.info(f"[accounts_token_obtain] Token obtained successfully username={username}")
            return Response(serializer.validated_data)
        except DRFValidationError as e:
            logger.warning(f"[accounts_token_obtain] Validation error username={username} error={str(e)}")
            raise
        except Exception as e:
            logger.error(f"[accounts_token_obtain] Unexpected error username={username} error={str(e)}")
            raise


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

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
        """
        Create a new user account and generate JWT tokens.

        This method handles user registration with atomic transaction to ensure
        data consistency. Upon successful creation, it generates both refresh
        and access tokens for immediate authentication.

        Returns:
            Response containing user data and JWT tokens (refresh + access)
        """
        email = request.data.get("email")
        username = request.data.get("username")
        logger.info(f"[accounts_user_create] User registration request email={email} username={username}")
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            with transaction.atomic():
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
            logger.info(f"[accounts_user_create] User created successfully id={user.id} email={user.email} username={username}")

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
        except DRFValidationError as e:
            logger.warning(f"[accounts_user_create] Validation error email={email} username={username} errors={e.detail}")
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError as e:
            logger.error(f"[accounts_user_create] Integrity error email={email} username={username} error={str(e)}")
            return Response(
                {"error": "Un utilisateur avec cet email ou ce nom d'utilisateur existe déjà"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[accounts_user_create] Unexpected error email={email} username={username} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la création du compte"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def list(self, request, *args, **kwargs):
        logger.info("[accounts_user_list] User list request")
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[accounts_user_list] Error listing users, error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la récupération des utilisateurs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        user_id = kwargs.get("pk")
        logger.info(f"[accounts_user_retrieve] User retrieve request id={user_id}")
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[accounts_user_retrieve] Error retrieving user id={user_id} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la récupération de l'utilisateur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, *args, **kwargs):
        user_id = kwargs.get("pk")
        logger.info(f"[accounts_user_update] User update request id={user_id}")
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(f"[accounts_user_update] User updated successfully id={user_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[accounts_user_update] Validation error id={user_id} errors={e.detail}")
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError as e:
            logger.error(f"[accounts_user_update] Integrity error id={user_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[accounts_user_update] Unexpected error id={user_id} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la mise à jour de l'utilisateur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def partial_update(self, request, *args, **kwargs):
        user_id = kwargs.get("pk")
        logger.info(f"[accounts_user_partial_update] User partial update request id={user_id}")
        try:
            response = super().partial_update(request, *args, **kwargs)
            logger.info(f"[accounts_user_partial_update] User partially updated successfully id={user_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[accounts_user_partial_update] Validation error id={user_id} errors={e.detail}")
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError as e:
            logger.error(f"[accounts_user_partial_update] Integrity error id={user_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[accounts_user_partial_update] Unexpected error id={user_id} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la mise à jour partielle de l'utilisateur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        user_id = kwargs.get("pk")
        logger.info(f"[accounts_user_destroy] User delete request id={user_id}")
        try:
            response = super().destroy(request, *args, **kwargs)
            logger.info(f"[accounts_user_destroy] User deleted successfully id={user_id}")
            return response
        except Exception as e:
            logger.error(f"[accounts_user_destroy] Error deleting user id={user_id} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la suppression de l'utilisateur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def me(self, request):
        user_id = request.user.id if request.user.is_authenticated else None
        if not user_id:
            return Response(
                {"error": "Utilisateur non authentifié"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        logger.info(f"[accounts_user_me] Get current user info id={user_id}")
        try:
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"[accounts_user_me] Error getting user info id={user_id} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la récupération des informations utilisateur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        """
        Change the authenticated user's password and regenerate JWT tokens.

        This method validates the old password, updates it with the new one
        using an atomic transaction, and generates new tokens to invalidate
        any existing sessions.

        Returns:
            Response containing success message and new JWT tokens
        """
        user_id = request.user.id
        logger.info(f"[accounts_user_change_password] Password change request id={user_id}")
        try:
            serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)

            user = request.user
            with transaction.atomic():
                user.set_password(serializer.validated_data["new_password"])
                user.save()
                refresh = RefreshToken.for_user(user)

            logger.info(f"[accounts_user_change_password] Password changed successfully id={user_id}")

            return Response(
                {
                    "message": "Mot de passe modifié avec succès",
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                }
            )
        except DRFValidationError as e:
            logger.warning(f"[accounts_user_change_password] Validation error id={user_id} errors={e.detail}")
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[accounts_user_change_password] Unexpected error id={user_id} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors du changement de mot de passe"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["patch"])
    def update_profile(self, request):
        user_id = request.user.id
        logger.info(f"[accounts_user_update_profile] Profile update request id={user_id}")
        try:
            serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            logger.info(f"[accounts_user_update_profile] Profile updated successfully id={user_id}")

            return Response(UserSerializer(request.user).data)
        except DRFValidationError as e:
            logger.warning(f"[accounts_user_update_profile] Validation error id={user_id} errors={e.detail}")
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError as e:
            logger.error(f"[accounts_user_update_profile] Integrity error id={user_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[accounts_user_update_profile] Unexpected error id={user_id} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la mise à jour"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TokenLogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = []

    def post(self, request):
        user_id = request.user.id
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            logout(request)
            logger.info(f"[accounts_token_logout] User logged out successfully id={user_id}")
            return Response({"message": "Déconnexion réussie"}, status=status.HTTP_200_OK)
        except TokenError:
            logger.warning(f"[accounts_token_logout] Invalid or missing refresh token id={user_id}")
            return Response(
                {"error": "Token invalide ou manquant"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[accounts_token_logout] Logout error id={user_id} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la déconnexion"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
