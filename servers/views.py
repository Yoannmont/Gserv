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

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Démarrer un serveur"""
        server = self.get_object()

        if server.status == "running":
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

        return Response({"message": "Démarrage du serveur en cours"})

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        """Arrêter un serveur"""
        server = self.get_object()

        if server.status == "stopped":
            return Response(
                {"error": "Le serveur est déjà arrêté"}, status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: Implémenter l'arrêt Docker
        server.status = "stopping"
        server.save()

        ServerStatus.objects.create(
            server=server, status="stopping", message="Arrêt du serveur", triggered_by=request.user
        )

        return Response({"message": "Arrêt du serveur en cours"})

    @action(detail=True, methods=["post"])
    def restart(self, request, pk=None):
        """Redémarrer un serveur"""
        server = self.get_object()

        # TODO: Implémenter le redémarrage Docker
        server.status = "stopping"
        server.save()

        ServerStatus.objects.create(
            server=server,
            status="stopping",
            message="Redémarrage du serveur",
            triggered_by=request.user,
        )

        return Response({"message": "Redémarrage du serveur en cours"})

    @action(detail=True, methods=["post"])
    def update_server(self, request, pk=None):
        """Mettre à jour un serveur"""
        server = self.get_object()
        force = request.data.get("force", False)

        if server.status == "running" and not force:
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

        return Response({"message": "Mise à jour du serveur en cours"})

    @action(detail=True, methods=["get"])
    def status_history(self, request, pk=None):
        """Historique des statuts d'un serveur"""
        server = self.get_object()
        history = server.status_history.all()[:50]  # 50 derniers statuts
        serializer = ServerStatusSerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        """Récupérer les logs d'un serveur"""
        server = self.get_object()

        # TODO: Implémenter la récupération des logs Docker
        return Response({"logs": "Logs Docker à implémenter", "container_id": server.container_id})

    @action(detail=True, methods=["get", "post"])
    def mods(self, request, pk=None):
        """Gérer les mods d'un serveur"""
        server = self.get_object()

        if request.method == "GET":
            mods = server.installed_mods.all()
            serializer = ServerModSerializer(mods, many=True)
            return Response(serializer.data)

        # POST: Installer un mod
        try:
            serializer = ServerModSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(server=server)
        except Exception as e:
            print("q>>>>", repr(e))
            raise
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post", "delete"], url_path="mods/(?P<mod_id>[^/.]+)")
    def mod_detail(self, request, pk=None, mod_id=None):
        """Gérer un mod spécifique"""
        server = self.get_object()
        server_mod = get_object_or_404(ServerMod, server=server, id=mod_id)

        if request.method == "GET":
            serializer = ServerModSerializer(server_mod)
            return Response(serializer.data)

        if request.method == "DELETE":
            server_mod.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        # PATCH/PUT: Mettre à jour le mod
        serializer = ServerModSerializer(server_mod, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @action(detail=True, methods=["get", "post"])
    def players(self, request, pk=None):
        """Gérer les joueurs d'un serveur"""
        server = self.get_object()

        if request.method == "GET":
            players = server.players.all()
            serializer = ServerPlayerSerializer(players, many=True)
            return Response(serializer.data)

        # POST: Ajouter un joueur
        serializer = ServerPlayerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(server=server)

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
