import logging

from django.db import models
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
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
    """Permission : propriétaire du serveur ou admin"""

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
        # Utilisateurs normaux voient leurs serveurs + serveurs publics
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
        """List server instances"""
        logger.info("[servers_instance_list] Server instance list request")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create server instance"""
        logger.info("[servers_instance_create] Server instance create request")
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            server_id = response.data.get("id", "unknown")
            logger.info(
                f"[servers_instance_create] Server instance created successfully id={server_id}"
            )
        return response

    def retrieve(self, request, *args, **kwargs):
        """Get server instance details"""
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_retrieve] Server instance retrieve request id={server_id}")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update server instance"""
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_update] Server instance update request id={server_id}")
        response = super().update(request, *args, **kwargs)
        logger.info(
            f"[servers_instance_update] Server instance updated successfully id={server_id}"
        )
        return response

    def partial_update(self, request, *args, **kwargs):
        """Partial update server instance"""
        server_id = kwargs.get("pk")
        logger.info(
            f"[servers_instance_partial_update] Server instance partial update request id={server_id}"
        )
        response = super().partial_update(request, *args, **kwargs)
        logger.info(
            f"[servers_instance_partial_update] Server instance partially updated successfully id={server_id}"
        )
        return response

    def destroy(self, request, *args, **kwargs):
        """Delete server instance"""
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_destroy] Server instance delete request id={server_id}")
        response = super().destroy(request, *args, **kwargs)
        logger.info(
            f"[servers_instance_destroy] Server instance deleted successfully id={server_id}"
        )
        return response

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Démarrer un serveur"""
        server = self.get_object()
        logger.info(f"[servers_instance_start] Server start request id={pk}")

        if server.status == "running":
            logger.warning(f"[servers_instance_start] Server already running id={pk}")
            return Response(
                {"error": "Le serveur est déjà en cours d'exécution"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # TODO: Implémenter le démarrage Docker
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

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        """Arrêter un serveur"""
        server = self.get_object()
        logger.info(f"[servers_instance_stop] Server stop request id={pk}")

        if server.status == "stopped":
            logger.warning(f"[servers_instance_stop] Server already stopped id={pk}")
            return Response(
                {"error": "Le serveur est déjà arrêté"}, status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: Implémenter l'arrêt Docker
        server.status = "stopping"
        server.save()

        ServerStatus.objects.create(
            server=server, status="stopping", message="Arrêt du serveur", triggered_by=request.user
        )
        logger.info(f"[servers_instance_stop] Server stop initiated id={pk}")

        return Response({"message": "Arrêt du serveur en cours"})

    @action(detail=True, methods=["post"])
    def restart(self, request, pk=None):
        """Redémarrer un serveur"""
        server = self.get_object()
        logger.info(f"[servers_instance_restart] Server restart request id={pk}")

        # TODO: Implémenter le redémarrage Docker
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

    @action(detail=True, methods=["post"])
    def update_server(self, request, pk=None):
        """Mettre à jour un serveur"""
        server = self.get_object()
        force = request.data.get("force", False)
        logger.info(f"[servers_instance_update_server] Server update request id={pk} force={force}")

        if server.status == "running" and not force:
            logger.warning(
                f"[servers_instance_update_server] Server must be stopped to update id={pk}"
            )
            return Response(
                {"error": "Le serveur doit être arrêté pour être mis à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # TODO: Implémenter la mise à jour Docker
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

    @action(detail=True, methods=["get"])
    def status_history(self, request, pk=None):
        """Historique des statuts d'un serveur"""
        server = self.get_object()
        logger.info(f"[servers_instance_status_history] Get server status history request id={pk}")
        history = server.status_history.all()[:50]  # 50 derniers statuts
        serializer = ServerStatusSerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        """Récupérer les logs d'un serveur"""
        server = self.get_object()
        logger.info(f"[servers_instance_logs] Get server logs request id={pk}")

        # TODO: Implémenter la récupération des logs Docker
        return Response({"logs": "Logs Docker à implémenter", "container_id": server.container_id})

    @action(detail=True, methods=["get", "post"])
    def mods(self, request, pk=None):
        """Gérer les mods d'un serveur"""
        server = self.get_object()

        if request.method == "GET":
            logger.info(f"[servers_instance_mods] Get server mods request id={pk}")
            mods = server.installed_mods.all()
            serializer = ServerModSerializer(mods, many=True)
            return Response(serializer.data)

        # POST: Installer un mod
        logger.info(f"[servers_instance_mods] Install server mod request id={pk}")
        try:
            serializer = ServerModSerializer(data=request.data)
            serializer.is_valid()
            print("p>>>>", serializer.validated_data)
            serializer.save(server=server)
            mod_id = serializer.data.get("id", "unknown")
            logger.info(
                f"[servers_instance_mods] Server mod installed successfully id={pk} mod_id={mod_id}"
            )
        except Exception as e:
            logger.error(f"[servers_instance_mods] Server mod install error id={pk} error={str(e)}")
            print("q>>>>", repr(e))
            raise
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post", "delete"], url_path="mods/(?P<mod_id>[^/.]+)")
    def mod_detail(self, request, pk=None, mod_id=None):
        """Gérer un mod spécifique"""
        server = self.get_object()
        server_mod = get_object_or_404(ServerMod, server=server, id=mod_id)

        if request.method == "GET":
            logger.info(
                f"[servers_instance_mod_detail] Get server mod detail request id={pk} mod_id={mod_id}"
            )
            serializer = ServerModSerializer(server_mod)
            return Response(serializer.data)

        if request.method == "DELETE":
            logger.info(
                f"[servers_instance_mod_detail] Delete server mod request id={pk} mod_id={mod_id}"
            )
            server_mod.delete()
            logger.info(
                f"[servers_instance_mod_detail] Server mod deleted successfully id={pk} mod_id={mod_id}"
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        # PATCH/PUT: Mettre à jour le mod
        logger.info(
            f"[servers_instance_mod_detail] Update server mod request id={pk} mod_id={mod_id}"
        )
        serializer = ServerModSerializer(server_mod, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(
            f"[servers_instance_mod_detail] Server mod updated successfully id={pk} mod_id={mod_id}"
        )

        return Response(serializer.data)

    @action(detail=True, methods=["get", "post"])
    def players(self, request, pk=None):
        """Gérer les joueurs d'un serveur"""
        server = self.get_object()

        if request.method == "GET":
            logger.info(f"[servers_instance_players] Get server players request id={pk}")
            players = server.players.all()
            serializer = ServerPlayerSerializer(players, many=True)
            return Response(serializer.data)

        # POST: Ajouter un joueur
        logger.info(f"[servers_instance_players] Add server player request id={pk}")
        serializer = ServerPlayerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(server=server)
        player_id = serializer.data.get("id", "unknown")
        logger.info(
            f"[servers_instance_players] Server player added successfully id={pk} player_id={player_id}"
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
        """List server mods"""
        logger.info("[servers_mod_list] Server mod list request")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create server mod"""
        logger.info("[servers_mod_create] Server mod create request")
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            mod_id = response.data.get("id", "unknown")
            logger.info(f"[servers_mod_create] Server mod created successfully id={mod_id}")
        return response

    def retrieve(self, request, *args, **kwargs):
        """Get server mod details"""
        mod_id = kwargs.get("pk")
        logger.info(f"[servers_mod_retrieve] Server mod retrieve request id={mod_id}")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update server mod"""
        mod_id = kwargs.get("pk")
        logger.info(f"[servers_mod_update] Server mod update request id={mod_id}")
        response = super().update(request, *args, **kwargs)
        logger.info(f"[servers_mod_update] Server mod updated successfully id={mod_id}")
        return response

    def partial_update(self, request, *args, **kwargs):
        """Partial update server mod"""
        mod_id = kwargs.get("pk")
        logger.info(f"[servers_mod_partial_update] Server mod partial update request id={mod_id}")
        response = super().partial_update(request, *args, **kwargs)
        logger.info(
            f"[servers_mod_partial_update] Server mod partially updated successfully id={mod_id}"
        )
        return response

    def destroy(self, request, *args, **kwargs):
        """Delete server mod"""
        mod_id = kwargs.get("pk")
        logger.info(f"[servers_mod_destroy] Server mod delete request id={mod_id}")
        response = super().destroy(request, *args, **kwargs)
        logger.info(f"[servers_mod_destroy] Server mod deleted successfully id={mod_id}")
        return response


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
        """List server players"""
        logger.info("[servers_player_list] Server player list request")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create server player"""
        logger.info("[servers_player_create] Server player create request")
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            player_id = response.data.get("id", "unknown")
            logger.info(
                f"[servers_player_create] Server player created successfully id={player_id}"
            )
        return response

    def retrieve(self, request, *args, **kwargs):
        """Get server player details"""
        player_id = kwargs.get("pk")
        logger.info(f"[servers_player_retrieve] Server player retrieve request id={player_id}")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update server player"""
        player_id = kwargs.get("pk")
        logger.info(f"[servers_player_update] Server player update request id={player_id}")
        response = super().update(request, *args, **kwargs)
        logger.info(f"[servers_player_update] Server player updated successfully id={player_id}")
        return response

    def partial_update(self, request, *args, **kwargs):
        """Partial update server player"""
        player_id = kwargs.get("pk")
        logger.info(
            f"[servers_player_partial_update] Server player partial update request id={player_id}"
        )
        response = super().partial_update(request, *args, **kwargs)
        logger.info(
            f"[servers_player_partial_update] Server player partially updated successfully id={player_id}"
        )
        return response

    def destroy(self, request, *args, **kwargs):
        """Delete server player"""
        player_id = kwargs.get("pk")
        logger.info(f"[servers_player_destroy] Server player delete request id={player_id}")
        response = super().destroy(request, *args, **kwargs)
        logger.info(f"[servers_player_destroy] Server player deleted successfully id={player_id}")
        return response
