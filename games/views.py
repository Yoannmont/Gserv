import logging

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

logger = logging.getLogger(__name__)


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

    def list(self, request, *args, **kwargs):
        """List games"""
        logger.info("[games_game_list] Game list request")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create game"""
        logger.info("[games_game_create] Game create request")
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            game_slug = response.data.get('slug', 'unknown')
            logger.info(f"[games_game_create] Game created successfully slug={game_slug}")
        return response

    def retrieve(self, request, *args, **kwargs):
        """Get game details"""
        slug = kwargs.get('slug')
        logger.info(f"[games_game_retrieve] Game retrieve request slug={slug}")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update game"""
        slug = kwargs.get('slug')
        logger.info(f"[games_game_update] Game update request slug={slug}")
        response = super().update(request, *args, **kwargs)
        logger.info(f"[games_game_update] Game updated successfully slug={slug}")
        return response

    def partial_update(self, request, *args, **kwargs):
        """Partial update game"""
        slug = kwargs.get('slug')
        logger.info(f"[games_game_partial_update] Game partial update request slug={slug}")
        response = super().partial_update(request, *args, **kwargs)
        logger.info(f"[games_game_partial_update] Game partially updated successfully slug={slug}")
        return response

    def destroy(self, request, *args, **kwargs):
        """Delete game"""
        slug = kwargs.get('slug')
        logger.info(f"[games_game_destroy] Game delete request slug={slug}")
        response = super().destroy(request, *args, **kwargs)
        logger.info(f"[games_game_destroy] Game deleted successfully slug={slug}")
        return response

    @action(detail=True, methods=["get"])
    def versions(self, request, slug=None):
        """Liste des versions disponibles pour un jeu"""
        game = self.get_object()
        logger.info(f"[games_game_versions] Get game versions request slug={slug}")
        versions = game.versions.all()
        serializer = GameVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def mods(self, request, slug=None):
        """Liste des mods disponibles pour un jeu"""
        game = self.get_object()
        version = request.query_params.get("version")
        logger.info(f"[games_game_mods] Get game mods request slug={slug} version={version}")
        mods = game.mods.filter(is_active=True)

        # Filtrage optionnel par version
        if version:
            mods = mods.filter(compatible_game_versions__version=version)

        serializer = GameModSerializer(mods, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def configurations(self, request, slug=None):
        """Liste des configurations disponibles pour un jeu"""
        game = self.get_object()
        logger.info(f"[games_game_configurations] Get game configurations request slug={slug}")
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

    def list(self, request, *args, **kwargs):
        """List game versions"""
        logger.info("[games_version_list] Game version list request")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create game version"""
        logger.info("[games_version_create] Game version create request")
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            version_id = response.data.get('id', 'unknown')
            logger.info(f"[games_version_create] Game version created successfully id={version_id}")
        return response

    def retrieve(self, request, *args, **kwargs):
        """Get game version details"""
        version_id = kwargs.get('pk')
        logger.info(f"[games_version_retrieve] Game version retrieve request id={version_id}")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update game version"""
        version_id = kwargs.get('pk')
        logger.info(f"[games_version_update] Game version update request id={version_id}")
        response = super().update(request, *args, **kwargs)
        logger.info(f"[games_version_update] Game version updated successfully id={version_id}")
        return response

    def partial_update(self, request, *args, **kwargs):
        """Partial update game version"""
        version_id = kwargs.get('pk')
        logger.info(f"[games_version_partial_update] Game version partial update request id={version_id}")
        response = super().partial_update(request, *args, **kwargs)
        logger.info(f"[games_version_partial_update] Game version partially updated successfully id={version_id}")
        return response

    def destroy(self, request, *args, **kwargs):
        """Delete game version"""
        version_id = kwargs.get('pk')
        logger.info(f"[games_version_destroy] Game version delete request id={version_id}")
        response = super().destroy(request, *args, **kwargs)
        logger.info(f"[games_version_destroy] Game version deleted successfully id={version_id}")
        return response


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

    def list(self, request, *args, **kwargs):
        """List game mods"""
        logger.info("[games_mod_list] Game mod list request")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create game mod"""
        logger.info("[games_mod_create] Game mod create request")
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            mod_id = response.data.get('id', 'unknown')
            logger.info(f"[games_mod_create] Game mod created successfully id={mod_id}")
        return response

    def retrieve(self, request, *args, **kwargs):
        """Get game mod details"""
        mod_id = kwargs.get('pk')
        logger.info(f"[games_mod_retrieve] Game mod retrieve request id={mod_id}")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update game mod"""
        mod_id = kwargs.get('pk')
        logger.info(f"[games_mod_update] Game mod update request id={mod_id}")
        response = super().update(request, *args, **kwargs)
        logger.info(f"[games_mod_update] Game mod updated successfully id={mod_id}")
        return response

    def partial_update(self, request, *args, **kwargs):
        """Partial update game mod"""
        mod_id = kwargs.get('pk')
        logger.info(f"[games_mod_partial_update] Game mod partial update request id={mod_id}")
        response = super().partial_update(request, *args, **kwargs)
        logger.info(f"[games_mod_partial_update] Game mod partially updated successfully id={mod_id}")
        return response

    def destroy(self, request, *args, **kwargs):
        """Delete game mod"""
        mod_id = kwargs.get('pk')
        logger.info(f"[games_mod_destroy] Game mod delete request id={mod_id}")
        response = super().destroy(request, *args, **kwargs)
        logger.info(f"[games_mod_destroy] Game mod deleted successfully id={mod_id}")
        return response


class GameConfigurationViewSet(viewsets.ModelViewSet):
    queryset = GameConfiguration.objects.all()
    serializer_class = GameConfigurationSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["game", "is_default"]

    def list(self, request, *args, **kwargs):
        """List game configurations"""
        logger.info("[games_config_list] Game configuration list request")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create game configuration"""
        logger.info("[games_config_create] Game configuration create request")
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            config_id = response.data.get('id', 'unknown')
            logger.info(f"[games_config_create] Game configuration created successfully id={config_id}")
        return response

    def retrieve(self, request, *args, **kwargs):
        """Get game configuration details"""
        config_id = kwargs.get('pk')
        logger.info(f"[games_config_retrieve] Game configuration retrieve request id={config_id}")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update game configuration"""
        config_id = kwargs.get('pk')
        logger.info(f"[games_config_update] Game configuration update request id={config_id}")
        response = super().update(request, *args, **kwargs)
        logger.info(f"[games_config_update] Game configuration updated successfully id={config_id}")
        return response

    def partial_update(self, request, *args, **kwargs):
        """Partial update game configuration"""
        config_id = kwargs.get('pk')
        logger.info(f"[games_config_partial_update] Game configuration partial update request id={config_id}")
        response = super().partial_update(request, *args, **kwargs)
        logger.info(f"[games_config_partial_update] Game configuration partially updated successfully id={config_id}")
        return response

    def destroy(self, request, *args, **kwargs):
        """Delete game configuration"""
        config_id = kwargs.get('pk')
        logger.info(f"[games_config_destroy] Game configuration delete request id={config_id}")
        response = super().destroy(request, *args, **kwargs)
        logger.info(f"[games_config_destroy] Game configuration deleted successfully id={config_id}")
        return response
