import logging

from django.db import IntegrityError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from games.models import Game, GameConfiguration, GameVersion
from games.serializers import (
    GameConfigurationSerializer,
    GameDetailSerializer,
    GameSerializer,
    GameVersionSerializer,
)

logger = logging.getLogger(__name__)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_admin


class GameViewSet(viewsets.ModelViewSet):
    queryset = Game.objects.filter(is_active=True)
    serializer_class = GameSerializer
    permission_classes = [IsAdminOrReadOnly]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
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
        logger.info("[games_game_list] Game list request")
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[games_game_list] Error listing games error={str(e)}")
            raise

    def create(self, request, *args, **kwargs):
        name = request.data.get("name", "unknown")
        logger.info(f"[games_game_create] Game create request name={name}")
        try:
            response = super().create(request, *args, **kwargs)
            if response.status_code == 201:
                game_slug = response.data.get("slug", "unknown")
                logger.info(f"[games_game_create] Game created successfully slug={game_slug} name={name}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[games_game_create] Validation error name={name} errors={e.detail}")
            return Response({"error": "Erreur de validation", "details": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError as e:
            logger.error(f"[games_game_create] Integrity error name={name} error={str(e)}")
            return Response(
                {"error": "Un jeu avec ce nom ou ce slug existe déjà"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[games_game_create] Unexpected error name={name} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la création du jeu"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        logger.info(f"[games_game_retrieve] Game retrieve request slug={slug}")
        try:
            return super().retrieve(request, *args, **kwargs)
        except NotFound:
            logger.warning(f"[games_game_retrieve] Game not found slug={slug}")
            return Response({"error": "Jeu non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[games_game_retrieve] Error retrieving game slug={slug} error={str(e)}")
            return Response({"error": "Erreur lors de la récupération du jeu"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        logger.info(f"[games_game_update] Game update request slug={slug}")
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(f"[games_game_update] Game updated successfully slug={slug}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[games_game_update] Validation error slug={slug} errors={e.detail}")
            return Response({"error": "Erreur de validation", "details": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except NotFound:
            logger.warning(f"[games_game_update] Game not found slug={slug}")
            return Response({"error": "Jeu non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            logger.error(f"[games_game_update] Integrity error slug={slug} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[games_game_update] Unexpected error slug={slug} error={str(e)}")
            raise

    def partial_update(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        logger.info(f"[games_game_partial_update] Game partial update request slug={slug}")
        try:
            response = super().partial_update(request, *args, **kwargs)
            logger.info(f"[games_game_partial_update] Game partially updated successfully slug={slug}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[games_game_partial_update] Validation error slug={slug} errors={e.detail}")
            return Response({"error": "Erreur de validation", "details": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except NotFound:
            logger.warning(f"[games_game_partial_update] Game not found slug={slug}")
            return Response({"error": "Jeu non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            logger.error(f"[games_game_partial_update] Integrity error slug={slug} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[games_game_partial_update] Unexpected error slug={slug} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la mise à jour partielle du jeu"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        logger.info(f"[games_game_destroy] Game delete request slug={slug}")
        try:
            response = super().destroy(request, *args, **kwargs)
            logger.info(f"[games_game_destroy] Game deleted successfully slug={slug}")
            return response
        except NotFound:
            logger.warning(f"[games_game_destroy] Game not found slug={slug}")
            return Response({"error": "Jeu non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[games_game_destroy] Error deleting game slug={slug} error={str(e)}")
            return Response({"error": "Erreur lors de la suppression du jeu"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["get"])
    def versions(self, request, slug=None):
        logger.info(f"[games_game_versions] Get game versions request slug={slug}")
        try:
            game = self.get_object()
            versions = game.versions.all()
            serializer = GameVersionSerializer(versions, many=True)
            return Response(serializer.data)
        except NotFound:
            logger.warning(f"[games_game_versions] Game not found slug={slug}")
            return Response({"error": "Jeu non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[games_game_versions] Error getting versions slug={slug} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la récupération des versions"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def configurations(self, request, slug=None):
        logger.info(f"[games_game_configurations] Get game configurations request slug={slug}")
        try:
            game = self.get_object()
            configs = game.configurations.all()
            serializer = GameConfigurationSerializer(configs, many=True)
            return Response(serializer.data)
        except NotFound:
            logger.warning(f"[games_game_configurations] Game not found slug={slug}")
            return Response({"error": "Jeu non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[games_game_configurations] Error getting configurations slug={slug} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la récupération des configurations"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GameVersionViewSet(viewsets.ModelViewSet):
    queryset = GameVersion.objects.all()
    serializer_class = GameVersionSerializer
    permission_classes = [IsAdminOrReadOnly]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["game", "is_stable", "is_recommended"]
    ordering_fields = ["release_date", "version"]
    ordering = ["-release_date"]

    def list(self, request, *args, **kwargs):
        logger.info("[games_version_list] Game version list request")
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[games_version_list] Error listing versions error={str(e)}")
            raise

    def create(self, request, *args, **kwargs):
        version = request.data.get("version", "unknown")
        logger.info(f"[games_version_create] Game version create request version={version}")
        try:
            response = super().create(request, *args, **kwargs)
            if response.status_code == 201:
                version_id = response.data.get("id", "unknown")
                logger.info(f"[games_version_create] Game version created successfully id={version_id} version={version}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[games_version_create] Validation error version={version} errors={e.detail}")
            return Response({"error": "Erreur de validation", "details": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError as e:
            logger.error(f"[games_version_create] Integrity error version={version} error={str(e)}")
            return Response(
                {"error": "Une version avec ce numéro existe déjà pour ce jeu"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[games_version_create] Unexpected error version={version} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la création de la version"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        version_id = kwargs.get("pk")
        logger.info(f"[games_version_retrieve] Game version retrieve request id={version_id}")
        try:
            return super().retrieve(request, *args, **kwargs)
        except NotFound:
            logger.warning(f"[games_version_retrieve] Version not found id={version_id}")
            return Response({"error": "Version non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[games_version_retrieve] Error retrieving version id={version_id} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la récupération de la version"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        version_id = kwargs.get("pk")
        logger.info(f"[games_version_update] Game version update request id={version_id}")
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(f"[games_version_update] Game version updated successfully id={version_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[games_version_update] Validation error id={version_id} errors={e.detail}")
            return Response({"error": "Erreur de validation", "details": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except NotFound:
            logger.warning(f"[games_version_update] Version not found id={version_id}")
            return Response({"error": "Version non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            logger.error(f"[games_version_update] Integrity error id={version_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[games_version_update] Unexpected error id={version_id} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la mise à jour de la version"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def partial_update(self, request, *args, **kwargs):
        version_id = kwargs.get("pk")
        logger.info(f"[games_version_partial_update] Game version partial update request id={version_id}")
        try:
            response = super().partial_update(request, *args, **kwargs)
            logger.info(f"[games_version_partial_update] Game version partially updated successfully id={version_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[games_version_partial_update] Validation error id={version_id} errors={e.detail}")
            return Response({"error": "Erreur de validation", "details": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except NotFound:
            logger.warning(f"[games_version_partial_update] Version not found id={version_id}")
            return Response({"error": "Version non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            logger.error(f"[games_version_partial_update] Integrity error id={version_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[games_version_partial_update] Unexpected error id={version_id} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la mise à jour partielle de la version"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        version_id = kwargs.get("pk")
        logger.info(f"[games_version_destroy] Game version delete request id={version_id}")
        try:
            response = super().destroy(request, *args, **kwargs)
            logger.info(f"[games_version_destroy] Game version deleted successfully id={version_id}")
            return response
        except NotFound:
            logger.warning(f"[games_version_destroy] Version not found id={version_id}")
            return Response({"error": "Version non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[games_version_destroy] Error deleting version id={version_id} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la suppression de la version"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GameConfigurationViewSet(viewsets.ModelViewSet):
    queryset = GameConfiguration.objects.all()
    serializer_class = GameConfigurationSerializer
    permission_classes = [IsAdminOrReadOnly]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["game", "is_default"]

    def list(self, request, *args, **kwargs):
        logger.info("[games_config_list] Game configuration list request")
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[games_config_list] Error listing configurations error={str(e)}")
            raise

    def create(self, request, *args, **kwargs):
        name = request.data.get("name", "unknown")
        logger.info(f"[games_config_create] Game configuration create request name={name}")
        try:
            response = super().create(request, *args, **kwargs)
            if response.status_code == 201:
                config_id = response.data.get("id", "unknown")
                logger.info(f"[games_config_create] Game configuration created successfully id={config_id} name={name}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[games_config_create] Validation error name={name} errors={e.detail}")
            return Response({"error": "Erreur de validation", "details": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError as e:
            logger.error(f"[games_config_create] Integrity error name={name} error={str(e)}")
            return Response(
                {"error": "Une configuration avec ce nom existe déjà pour ce jeu"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[games_config_create] Unexpected error name={name} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la création de la configuration"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        config_id = kwargs.get("pk")
        logger.info(f"[games_config_retrieve] Game configuration retrieve request id={config_id}")
        try:
            return super().retrieve(request, *args, **kwargs)
        except NotFound:
            logger.warning(f"[games_config_retrieve] Configuration not found id={config_id}")
            return Response({"error": "Configuration non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[games_config_retrieve] Error retrieving configuration id={config_id} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la récupération de la configuration"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        config_id = kwargs.get("pk")
        logger.info(f"[games_config_update] Game configuration update request id={config_id}")
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(f"[games_config_update] Game configuration updated successfully id={config_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[games_config_update] Validation error id={config_id} errors={e.detail}")
            return Response({"error": "Erreur de validation", "details": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except NotFound:
            logger.warning(f"[games_config_update] Configuration not found id={config_id}")
            return Response({"error": "Configuration non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            logger.error(f"[games_config_update] Integrity error id={config_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[games_config_update] Unexpected error id={config_id} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la mise à jour de la configuration"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def partial_update(self, request, *args, **kwargs):
        config_id = kwargs.get("pk")
        logger.info(f"[games_config_partial_update] Game configuration partial update request id={config_id}")
        try:
            response = super().partial_update(request, *args, **kwargs)
            logger.info(f"[games_config_partial_update] Game configuration partially updated successfully id={config_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[games_config_partial_update] Validation error id={config_id} errors={e.detail}")
            raise
        except NotFound:
            logger.warning(f"[games_config_partial_update] Configuration not found id={config_id}")
            return Response({"error": "Configuration non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            logger.error(f"[games_config_partial_update] Integrity error id={config_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[games_config_partial_update] Unexpected error id={config_id} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la mise à jour partielle de la configuration"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        config_id = kwargs.get("pk")
        logger.info(f"[games_config_destroy] Game configuration delete request id={config_id}")
        try:
            response = super().destroy(request, *args, **kwargs)
            logger.info(f"[games_config_destroy] Game configuration deleted successfully id={config_id}")
            return response
        except NotFound:
            logger.warning(f"[games_config_destroy] Configuration not found id={config_id}")
            return Response({"error": "Configuration non trouvée"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[games_config_destroy] Error deleting configuration id={config_id} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la suppression de la configuration"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
