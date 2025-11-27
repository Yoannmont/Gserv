import logging

from django.db import IntegrityError, models, transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from servers.models import ServerInstance, ServerMod, ServerPlayer, ServerStatus
from servers.serializers import (
    ServerInstanceCreateSerializer,
    ServerInstanceDetailSerializer,
    ServerInstanceListSerializer,
    ServerInstanceUpdateSerializer,
    ServerModSerializer,
    ServerPlayerSerializer,
    ServerStatusSerializer,
)

logger = logging.getLogger(__name__)


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        if hasattr(obj, "server"):
            return obj.server.owner == request.user
        return obj.owner == request.user


class ServerInstanceViewSet(viewsets.ModelViewSet):
    queryset = ServerInstance.objects.all()
    serializer_class = ServerInstanceListSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["game", "status", "is_public", "owner"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "last_started_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return ServerInstance.objects.all()
        return ServerInstance.objects.filter(models.Q(owner=user) | models.Q(is_public=True))

    def get_serializer_class(self):
        if self.action == "list":
            return ServerInstanceListSerializer
        if self.action == "create":
            return ServerInstanceCreateSerializer
        if self.action in ["update", "partial_update"]:
            return ServerInstanceUpdateSerializer
        return ServerInstanceDetailSerializer

    def list(self, request, *args, **kwargs):
        logger.info("[servers_instance_list] Server instance list request")
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[servers_instance_list] Error listing servers error={str(e)}")
            raise

    def create(self, request, *args, **kwargs):
        name = request.data.get("name", "unknown")
        logger.info(f"[servers_instance_create] Server instance create request name={name}")
        try:
            response = super().create(request, *args, **kwargs)
            if response.status_code == 201:
                server_id = response.data.get("id", "unknown")
                logger.info(
                    f"[servers_instance_create] Server instance created successfully id={server_id} name={name}"
                )
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_instance_create] Validation error name={name} errors={e.detail}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_create] Integrity error name={name} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la création du serveur"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_instance_create] Unexpected error name={name} error={str(e)}")
            raise

    def retrieve(self, request, *args, **kwargs):
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_retrieve] Server instance retrieve request id={server_id}")
        try:
            return super().retrieve(request, *args, **kwargs)
        except NotFound:
            logger.warning(f"[servers_instance_retrieve] Server not found id={server_id}")
            raise
        except Exception as e:
            logger.error(f"[servers_instance_retrieve] Error retrieving server id={server_id} error={str(e)}")
            raise

    def update(self, request, *args, **kwargs):
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_update] Server instance update request id={server_id}")
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(f"[servers_instance_update] Server instance updated successfully id={server_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_instance_update] Validation error id={server_id} errors={e.detail}")
            raise
        except NotFound:
            logger.warning(f"[servers_instance_update] Server not found id={server_id}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_update] Integrity error id={server_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_instance_update] Unexpected error id={server_id} error={str(e)}")
            raise

    def partial_update(self, request, *args, **kwargs):
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_partial_update] Server instance partial update request id={server_id}")
        try:
            response = super().partial_update(request, *args, **kwargs)
            logger.info(
                f"[servers_instance_partial_update] Server instance partially updated successfully id={server_id}"
            )
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_instance_partial_update] Validation error id={server_id} errors={e.detail}")
            raise
        except NotFound:
            logger.warning(f"[servers_instance_partial_update] Server not found id={server_id}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_partial_update] Integrity error id={server_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_instance_partial_update] Unexpected error id={server_id} error={str(e)}")
            raise

    def destroy(self, request, *args, **kwargs):
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_destroy] Server instance delete request id={server_id}")
        try:
            response = super().destroy(request, *args, **kwargs)
            logger.info(f"[servers_instance_destroy] Server instance deleted successfully id={server_id}")
            return response
        except NotFound:
            logger.warning(f"[servers_instance_destroy] Server not found id={server_id}")
            raise
        except Exception as e:
            logger.error(f"[servers_instance_destroy] Error deleting server id={server_id} error={str(e)}")
            raise

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        logger.info(f"[servers_instance_start] Server start request id={pk}")
        try:
            server = self.get_object()

            if server.status == "running":
                logger.warning(f"[servers_instance_start] Server already running id={pk}")
                return Response(
                    {"error": "Le serveur est déjà en cours d'exécution"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                server.status = "starting"
                server.save()

                ServerStatus.objects.create(
                    server=server,
                    status="starting",
                    message="Démarrage du serveur",
                    triggered_by=request.user,
                )
            logger.info(f"[servers_instance_start] Server start initiated id={pk}")

            return Response({"message": "Démarrage du serveur en cours"})
        except NotFound:
            logger.warning(f"[servers_instance_start] Server not found id={pk}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_start] Integrity error id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors du démarrage du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"[servers_instance_start] Unexpected error id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors du démarrage du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        logger.info(f"[servers_instance_stop] Server stop request id={pk}")
        try:
            server = self.get_object()

            if server.status == "stopped":
                logger.warning(f"[servers_instance_stop] Server already stopped id={pk}")
                return Response({"error": "Le serveur est déjà arrêté"}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                server.status = "stopping"
                server.save()

                ServerStatus.objects.create(
                    server=server, status="stopping", message="Arrêt du serveur", triggered_by=request.user
                )
            logger.info(f"[servers_instance_stop] Server stop initiated id={pk}")

            return Response({"message": "Arrêt du serveur en cours"})
        except NotFound:
            logger.warning(f"[servers_instance_stop] Server not found id={pk}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_stop] Integrity error id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors de l'arrêt du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"[servers_instance_stop] Unexpected error id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors de l'arrêt du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def restart(self, request, pk=None):
        logger.info(f"[servers_instance_restart] Server restart request id={pk}")
        try:
            server = self.get_object()

            with transaction.atomic():
                server.status = "stopping"
                server.save()

                ServerStatus.objects.create(
                    server=server,
                    status="stopping",
                    message="Redémarrage du serveur",
                    triggered_by=request.user,
                )
            logger.info(f"[servers_instance_restart] Server restart initiated id={pk}")

            return Response({"message": "Redémarrage du serveur en cours"})
        except NotFound:
            logger.warning(f"[servers_instance_restart] Server not found id={pk}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_restart] Integrity error id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors du redémarrage du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"[servers_instance_restart] Unexpected error id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors du redémarrage du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def update_server(self, request, pk=None):
        force = request.data.get("force", False)
        logger.info(f"[servers_instance_update_server] Server update request id={pk} force={force}")
        try:
            server = self.get_object()

            if server.status == "running" and not force:
                logger.warning(f"[servers_instance_update_server] Server must be stopped to update id={pk}")
                return Response(
                    {"error": "Le serveur doit être arrêté pour être mis à jour"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                server.status = "updating"
                server.save()

                ServerStatus.objects.create(
                    server=server,
                    status="updating",
                    message="Mise à jour du serveur",
                    triggered_by=request.user,
                )
            logger.info(f"[servers_instance_update_server] Server update initiated id={pk}")

            return Response({"message": "Mise à jour du serveur en cours"})
        except NotFound:
            logger.warning(f"[servers_instance_update_server] Server not found id={pk}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_update_server] Integrity error id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la mise à jour du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"[servers_instance_update_server] Unexpected error id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la mise à jour du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def status_history(self, request, pk=None):
        logger.info(f"[servers_instance_status_history] Get server status history request id={pk}")
        try:
            server = self.get_object()
            history = server.status_history.all()[:50]
            serializer = ServerStatusSerializer(history, many=True)
            return Response(serializer.data)
        except NotFound:
            logger.warning(f"[servers_instance_status_history] Server not found id={pk}")
            raise
        except Exception as e:
            logger.error(f"[servers_instance_status_history] Error getting status history id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la récupération de l'historique"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        logger.info(f"[servers_instance_logs] Get server logs request id={pk}")
        try:
            server = self.get_object()
            return Response({"logs": "Logs Docker à implémenter", "container_id": server.container_id})
        except NotFound:
            logger.warning(f"[servers_instance_logs] Server not found id={pk}")
            raise
        except Exception as e:
            logger.error(f"[servers_instance_logs] Error getting logs id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la récupération des logs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get", "post"])
    def mods(self, request, pk=None):
        try:
            server = self.get_object()

            if request.method == "GET":
                logger.info(f"[servers_instance_mods] Get server mods request id={pk}")
                mods = server.installed_mods.all()
                serializer = ServerModSerializer(mods, many=True)
                return Response(serializer.data)

            logger.info(f"[servers_instance_mods] Install server mod request id={pk}")
            serializer = ServerModSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(server=server)
            mod_id = serializer.data.get("id", "unknown")
            logger.info(f"[servers_instance_mods] Server mod installed successfully id={pk} mod_id={mod_id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except NotFound:
            logger.warning(f"[servers_instance_mods] Server not found id={pk}")
            raise
        except DRFValidationError as e:
            logger.warning(f"[servers_instance_mods] Validation error id={pk} errors={e.detail}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_mods] Integrity error id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors de l'installation du mod"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_instance_mods] Unexpected error id={pk} error={str(e)}")
            raise

    @action(detail=True, methods=["get", "post", "delete"], url_path="mods/(?P<mod_id>[^/.]+)")
    def mod_detail(self, request, pk=None, mod_id=None):
        logger.info(f"[servers_instance_mod_detail] Mod detail request id={pk} mod_id={mod_id} method={request.method}")
        try:
            server = self.get_object()
            server_mod = get_object_or_404(ServerMod, server=server, id=mod_id)

            if request.method == "GET":
                serializer = ServerModSerializer(server_mod)
                return Response(serializer.data)

            if request.method == "DELETE":
                server_mod.delete()
                logger.info(f"[servers_instance_mod_detail] Server mod deleted successfully id={pk} mod_id={mod_id}")
                return Response(status=status.HTTP_204_NO_CONTENT)

            serializer = ServerModSerializer(server_mod, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            logger.info(f"[servers_instance_mod_detail] Server mod updated successfully id={pk} mod_id={mod_id}")

            return Response(serializer.data)
        except NotFound:
            logger.warning(f"[servers_instance_mod_detail] Server or mod not found id={pk} mod_id={mod_id}")
            raise
        except DRFValidationError as e:
            logger.warning(f"[servers_instance_mod_detail] Validation error id={pk} mod_id={mod_id} errors={e.detail}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_mod_detail] Integrity error id={pk} mod_id={mod_id} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la mise à jour du mod"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_instance_mod_detail] Unexpected error id={pk} mod_id={mod_id} error={str(e)}")
            raise

    @action(detail=True, methods=["get", "post"])
    def players(self, request, pk=None):
        try:
            server = self.get_object()

            if request.method == "GET":
                logger.info(f"[servers_instance_players] Get server players request id={pk}")
                players = server.players.all()
                serializer = ServerPlayerSerializer(players, many=True)
                return Response(serializer.data)

            logger.info(f"[servers_instance_players] Add server player request id={pk}")
            serializer = ServerPlayerSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(server=server)
            player_id = serializer.data.get("id", "unknown")
            logger.info(f"[servers_instance_players] Server player added successfully id={pk} player_id={player_id}")

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except NotFound:
            logger.warning(f"[servers_instance_players] Server not found id={pk}")
            raise
        except DRFValidationError as e:
            logger.warning(f"[servers_instance_players] Validation error id={pk} errors={e.detail}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_players] Integrity error id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors de l'ajout du joueur"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_instance_players] Unexpected error id={pk} error={str(e)}")
            raise


class ServerModViewSet(viewsets.ModelViewSet):
    queryset = ServerMod.objects.all()
    serializer_class = ServerModSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return ServerMod.objects.all()
        return ServerMod.objects.filter(server__owner=user)

    def list(self, request, *args, **kwargs):
        logger.info("[servers_mod_list] Server mod list request")
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[servers_mod_list] Error listing server mods error={str(e)}")
            raise

    def create(self, request, *args, **kwargs):
        logger.info("[servers_mod_create] Server mod create request")
        try:
            response = super().create(request, *args, **kwargs)
            if response.status_code == 201:
                mod_id = response.data.get("id", "unknown")
                logger.info(f"[servers_mod_create] Server mod created successfully id={mod_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_mod_create] Validation error errors={e.detail}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_mod_create] Integrity error error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la création"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_mod_create] Unexpected error error={str(e)}")
            raise

    def retrieve(self, request, *args, **kwargs):
        mod_id = kwargs.get("pk")
        logger.info(f"[servers_mod_retrieve] Server mod retrieve request id={mod_id}")
        try:
            return super().retrieve(request, *args, **kwargs)
        except NotFound:
            logger.warning(f"[servers_mod_retrieve] Mod not found id={mod_id}")
            raise
        except Exception as e:
            logger.error(f"[servers_mod_retrieve] Error retrieving mod id={mod_id} error={str(e)}")
            raise

    def update(self, request, *args, **kwargs):
        mod_id = kwargs.get("pk")
        logger.info(f"[servers_mod_update] Server mod update request id={mod_id}")
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(f"[servers_mod_update] Server mod updated successfully id={mod_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_mod_update] Validation error id={mod_id} errors={e.detail}")
            raise
        except NotFound:
            logger.warning(f"[servers_mod_update] Mod not found id={mod_id}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_mod_update] Integrity error id={mod_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_mod_update] Unexpected error id={mod_id} error={str(e)}")
            raise

    def partial_update(self, request, *args, **kwargs):
        mod_id = kwargs.get("pk")
        logger.info(f"[servers_mod_partial_update] Server mod partial update request id={mod_id}")
        try:
            response = super().partial_update(request, *args, **kwargs)
            logger.info(f"[servers_mod_partial_update] Server mod partially updated successfully id={mod_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_mod_partial_update] Validation error id={mod_id} errors={e.detail}")
            raise
        except NotFound:
            logger.warning(f"[servers_mod_partial_update] Mod not found id={mod_id}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_mod_partial_update] Integrity error id={mod_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_mod_partial_update] Unexpected error id={mod_id} error={str(e)}")
            raise

    def destroy(self, request, *args, **kwargs):
        mod_id = kwargs.get("pk")
        logger.info(f"[servers_mod_destroy] Server mod delete request id={mod_id}")
        try:
            response = super().destroy(request, *args, **kwargs)
            logger.info(f"[servers_mod_destroy] Server mod deleted successfully id={mod_id}")
            return response
        except NotFound:
            logger.warning(f"[servers_mod_destroy] Mod not found id={mod_id}")
            raise
        except Exception as e:
            logger.error(f"[servers_mod_destroy] Error deleting mod id={mod_id} error={str(e)}")
            raise


class ServerPlayerViewSet(viewsets.ModelViewSet):
    queryset = ServerPlayer.objects.all()
    serializer_class = ServerPlayerSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["server", "permission_level", "is_banned"]
    search_fields = ["minecraft_username", "minecraft_uuid"]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return ServerPlayer.objects.all()
        return ServerPlayer.objects.filter(server__owner=user)

    def list(self, request, *args, **kwargs):
        logger.info("[servers_player_list] Server player list request")
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"[servers_player_list] Error listing players error={str(e)}")
            raise

    def create(self, request, *args, **kwargs):
        username = request.data.get("minecraft_username", "unknown")
        logger.info(f"[servers_player_create] Server player create request username={username}")
        try:
            response = super().create(request, *args, **kwargs)
            if response.status_code == 201:
                player_id = response.data.get("id", "unknown")
                logger.info(
                    f"[servers_player_create] Server player created successfully id={player_id} username={username}"
                )
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_player_create] Validation error username={username} errors={e.detail}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_player_create] Integrity error username={username} error={str(e)}")
            return Response(
                {"error": "Un joueur avec cet identifiant existe déjà pour ce serveur"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_player_create] Unexpected error username={username} error={str(e)}")
            raise

    def retrieve(self, request, *args, **kwargs):
        player_id = kwargs.get("pk")
        logger.info(f"[servers_player_retrieve] Server player retrieve request id={player_id}")
        try:
            return super().retrieve(request, *args, **kwargs)
        except NotFound:
            logger.warning(f"[servers_player_retrieve] Player not found id={player_id}")
            raise
        except Exception as e:
            logger.error(f"[servers_player_retrieve] Error retrieving player id={player_id} error={str(e)}")
            raise

    def update(self, request, *args, **kwargs):
        player_id = kwargs.get("pk")
        logger.info(f"[servers_player_update] Server player update request id={player_id}")
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(f"[servers_player_update] Server player updated successfully id={player_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_player_update] Validation error id={player_id} errors={e.detail}")
            raise
        except NotFound:
            logger.warning(f"[servers_player_update] Player not found id={player_id}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_player_update] Integrity error id={player_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_player_update] Unexpected error id={player_id} error={str(e)}")
            raise

    def partial_update(self, request, *args, **kwargs):
        player_id = kwargs.get("pk")
        logger.info(f"[servers_player_partial_update] Server player partial update request id={player_id}")
        try:
            response = super().partial_update(request, *args, **kwargs)
            logger.info(f"[servers_player_partial_update] Server player partially updated successfully id={player_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_player_partial_update] Validation error id={player_id} errors={e.detail}")
            raise
        except NotFound:
            logger.warning(f"[servers_player_partial_update] Player not found id={player_id}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_player_partial_update] Integrity error id={player_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_player_partial_update] Unexpected error id={player_id} error={str(e)}")
            raise

    def destroy(self, request, *args, **kwargs):
        player_id = kwargs.get("pk")
        logger.info(f"[servers_player_destroy] Server player delete request id={player_id}")
        try:
            response = super().destroy(request, *args, **kwargs)
            logger.info(f"[servers_player_destroy] Server player deleted successfully id={player_id}")
            return response
        except NotFound:
            logger.warning(f"[servers_player_destroy] Player not found id={player_id}")
            raise
        except Exception as e:
            logger.error(f"[servers_player_destroy] Error deleting player id={player_id} error={str(e)}")
            raise
