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


class CustomTokenObtainPairView(TokenObtainPairView):
    """Vue personnalisée pour l'obtention de tokens JWT"""

    serializer_class = TokenObtainSerializer


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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Générer les tokens JWT
        refresh = RefreshToken.for_user(user)

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

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Récupérer les informations de l'utilisateur connecté"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def login(self, request):
        """Connexion de l'utilisateur et obtention des tokens JWT"""
        serializer = TokenObtainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data)

    @action(detail=False, methods=["post"])
    def logout(self, request):
        """Déconnexion de l'utilisateur (blacklist du refresh token)"""
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            logout(request)
            return Response({"message": "Déconnexion réussie"}, status=status.HTTP_200_OK)
        except TokenError:
            return Response({"error": "Token invalide"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Erreur lors de la déconnexion; {e}"}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["post"])
    def refresh(self, request):
        """Rafraîchir le token d'accès"""
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data)

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        """Changer le mot de passe de l'utilisateur"""
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        # Générer de nouveaux tokens
        refresh = RefreshToken.for_user(user)

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
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(UserSerializer(request.user).data)
