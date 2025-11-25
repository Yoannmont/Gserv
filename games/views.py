from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from games.models import Game, GameConfiguration, GameMod, GameVersion
from games.serializers import (
    GameConfigurationSerializer,
    GameDetailSerializer,
    GameModCreateSerializer,
    GameModSerializer,
    GameSerializer,
    GameVersionSerializer,
)


class IsAdminOrReadOnly(permissions.BasePermission):
    """Permission personnalisée : lecture pour tous, écriture pour admin"""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_admin


class GameViewSet(viewsets.ModelViewSet):
    queryset = Game.objects.filter(is_active=True)
    serializer_class = GameSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GameDetailSerializer
        return GameSerializer

    @action(detail=True, methods=["get"])
    def versions(self, request, slug=None):
        """Liste des versions disponibles pour un jeu"""
        game = self.get_object()
        versions = game.versions.all()
        serializer = GameVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def mods(self, request, slug=None):
        """Liste des mods disponibles pour un jeu"""
        game = self.get_object()
        mods = game.mods.filter(is_active=True)

        # Filtrage optionnel par version
        version = request.query_params.get("version")
        if version:
            mods = mods.filter(compatible_game_versions__version=version)

        serializer = GameModSerializer(mods, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def configurations(self, request, slug=None):
        """Liste des configurations disponibles pour un jeu"""
        game = self.get_object()
        configs = game.configurations.all()
        serializer = GameConfigurationSerializer(configs, many=True)
        return Response(serializer.data)


class GameVersionViewSet(viewsets.ModelViewSet):
    queryset = GameVersion.objects.all()
    serializer_class = GameVersionSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["game", "is_stable", "is_recommended"]
    ordering_fields = ["release_date", "version"]
    ordering = ["-release_date"]


class GameModViewSet(viewsets.ModelViewSet):
    queryset = GameMod.objects.filter(is_active=True)
    serializer_class = GameModSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["game", "mod_type"]
    search_fields = ["name", "description", "author"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action == "create":
            return GameModCreateSerializer
        return GameModSerializer


class GameConfigurationViewSet(viewsets.ModelViewSet):
    queryset = GameConfiguration.objects.all()
    serializer_class = GameConfigurationSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["game", "is_default"]
