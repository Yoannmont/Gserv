import logging

from django.db import IntegrityError
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from games.models import Game
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
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError as e:
            logger.error(f"[games_game_create] Integrity error name={name} error={str(e)}")
            return Response(
                {"error": "Un jeu avec ce nom ou ce slug existe déjà"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[games_game_create] Unexpected error name={name} error={str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la création du jeu"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            return Response(
                {"error": "Erreur lors de la récupération du jeu"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        logger.info(f"[games_game_update] Game update request slug={slug}")
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(f"[games_game_update] Game updated successfully slug={slug}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[games_game_update] Validation error slug={slug} errors={e.detail}")
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
            return Response(
                {"error": "Erreur lors de la suppression du jeu"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
