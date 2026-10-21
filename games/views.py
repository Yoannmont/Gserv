import logging

from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from games.models import Game
from games.serializers import (
    GameConfigurationSerializer,
    GameDetailSerializer,
    GameSerializer,
    GameVersionSerializer,
)

logger = logging.getLogger(__name__)


class GameViewSet(
    viewsets.GenericViewSet,
    viewsets.mixins.ListModelMixin,
    viewsets.mixins.RetrieveModelMixin,
):
    queryset = Game.objects.filter(is_active=True)
    serializer_class = GameSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]
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
