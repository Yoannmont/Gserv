import logging
import traceback

from celery import chain
from django.db import IntegrityError, models
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

import docker_manager
import docker_manager.services
import docker_manager.services.server_manager
from docker_manager.tasks import (
    create_server_task,
    full_reset_server_task,
    restart_server_task,
    start_server_task,
    stop_server_task,
    update_server_task,
)
from servers.models import ServerInstance, ServerMetrics, ServerStatus
from servers.serializers import (
    ServerInstanceCreateSerializer,
    ServerInstanceDetailSerializer,
    ServerInstanceListSerializer,
    ServerInstanceUpdateSerializer,
    ServerMetricsSerializer,
    ServerRoleSerializer,
    ServerStatusSerializer,
)

logger = logging.getLogger(__name__)


class IsServerRole(permissions.BasePermission):
    """Permission to check if a user can manage a server"""

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True

        if obj.owner == request.user:
            return True

        try:
            role = obj.roles.get(user=request.user)
            if view.action in [
                "list",
                "retrieve",
                "status_history",
                "logs",
                "metrics",
                "roles",
            ]:
                return role.can_view
            elif view.action in ["update", "partial_update"]:
                return role.can_edit
            elif view.action in [
                "start",
                "stop",
                "restart",
                "update_server",
                "full_reset",
            ]:
                return role.can_control
            elif view.action == "destroy":
                return role.can_delete
            return role.can_view
        except obj.roles.model.DoesNotExist:
            pass

        # Public servers are visible in read-only for GET actions
        if obj.is_public and request.method in permissions.SAFE_METHODS:
            if view.action in ["list", "retrieve", "status_history", "logs", "metrics"]:
                return True

        return False


class ServerInstanceViewSet(viewsets.ModelViewSet):
    queryset = ServerInstance.objects.all()
    serializer_class = ServerInstanceListSerializer
    permission_classes = [permissions.IsAuthenticated, IsServerRole]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["game", "status", "is_public", "owner"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "last_started_at"]
    ordering = ["-created_at"]
    SERVER_MANAGER = docker_manager.services.server_manager.get_server_manager()

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return ServerInstance.objects.all()
        return ServerInstance.objects.prefetch_related("roles").filter(
            models.Q(owner=user) | models.Q(is_public=True) | models.Q(roles__user=user, roles__can_view=True)
        )

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
            return Response(
                {"error": "Erreur lors de la récupération des serveurs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create(self, request, *args, **kwargs):
        name = request.data.get("name")
        logger.info(f"[servers_instance_create] Server instance create request name={name}")
        try:
            response = super().create(request, *args, **kwargs)
            if response.status_code == 201:
                server_id = response.data.get("id")
                user_id = request.user.id
                direct_launch = request.data.get("direct_launch", False)
                server = ServerInstance.objects.get(id=server_id)
                logger.info(f"[servers_instance_create] Server instance created successfully id={server_id} name={name}")
                # Create server instance
                if not direct_launch:
                    create_server_task.delay(server_id)
                else:
                    # then launch it
                    chain(
                        create_server_task.si(server_id),
                        start_server_task.si(server_id, user_id),
                    ).delay()
                ServerStatus.objects.create(
                    server=server,
                    status=ServerInstance.CREATING,
                    message="Création du serveur demandée",
                    triggered_by=request.user,
                )
                return response
            raise Exception("Server creation failed")
        except DRFValidationError as e:
            logger.warning(f"[servers_instance_create] Validation error name={name} errors={e.detail}")
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError as e:
            logger.error(f"[servers_instance_create] Integrity error name={name} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la création du serveur"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.error(f"[servers_instance_create] Unexpected error name={name} error={traceback.format_exc()}")
            return Response(
                {"error": "Erreur lors de la création du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_retrieve] Server instance retrieve request id={server_id}")
        try:
            return super().retrieve(request, *args, **kwargs)
        except NotFound:
            logger.warning(f"[servers_instance_retrieve] Server not found id={server_id}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, *args, **kwargs):
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_update] Server instance update request id={server_id}")
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(f"[servers_instance_update] Server instance updated successfully id={server_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_instance_update] Validation error id={server_id} errors={e.detail}")
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except NotFound:
            logger.warning(f"[servers_instance_update] Server not found id={server_id}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            logger.error(f"[servers_instance_update] Integrity error id={server_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_instance_update] Unexpected error id={server_id} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la mise à jour du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def partial_update(self, request, *args, **kwargs):
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_partial_update] Server instance partial update request id={server_id}")
        try:
            response = super().partial_update(request, *args, **kwargs)
            logger.info(f"[servers_instance_partial_update] Server instance partially updated successfully id={server_id}")
            return response
        except DRFValidationError as e:
            logger.warning(f"[servers_instance_partial_update] Validation error id={server_id} errors={e.detail}")
            return Response(
                {"error": "Erreur de validation", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except NotFound:
            logger.warning(f"[servers_instance_partial_update] Server not found id={server_id}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            logger.error(f"[servers_instance_partial_update] Integrity error id={server_id} error={str(e)}")
            return Response(
                {"error": "Erreur de contrainte d'intégrité lors de la mise à jour"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_instance_partial_update] Unexpected error id={server_id} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la mise à jour partielle du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        server_id = kwargs.get("pk")
        logger.info(f"[servers_instance_destroy] Server instance delete request id={server_id}")
        try:
            response = super().destroy(request, *args, **kwargs)
            logger.info(f"[servers_instance_destroy] Server instance deleted successfully id={server_id}")
            return response
        except NotFound:
            logger.warning(f"[servers_instance_destroy] Server not found id={server_id}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except ServerInstance.DoesNotExist:
            logger.warning(f"[servers_instance_destroy] Server not found id={server_id}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[servers_instance_destroy] Error deleting server id={server_id} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la suppression du serveur"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """
        Start a server instance.

        This method initiates the server startup process asynchronously.
        The server status will be updated to STARTING, and a background task
        will handle the actual Docker container startup.

        Returns:
            Response with success message or error if server is already running
        """
        logger.info(f"[servers_instance_start] Server start request id={pk}")
        try:
            server = self.get_object()

            if server.is_running:
                logger.warning(f"[servers_instance_start] Server already running id={pk}")
                return Response(
                    {"error": "Le serveur est déjà en cours d'exécution"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            start_server_task.delay(server.pk, request.user.id)

            ServerStatus.objects.create(
                server=server,
                status=ServerInstance.STARTING,
                message="Démarrage du serveur demandé",
                triggered_by=request.user,
            )
            logger.info(f"[servers_instance_start] Server start initiated id={pk}")

            return Response({"message": "Démarrage du serveur en cours"})
        except NotFound:
            logger.warning(f"[servers_instance_start] Server not found id={pk}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
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
    def full_reset(self, request, pk=None):
        """
        Full reset of a server: delete and recreate it, then start it.

        This is a destructive operation that will delete the current server
        container and data (if delete_data=True), then recreate and start it.

        Request Body:
            delete_data (bool, optional): If True, also delete server data files

        Returns:
            Response with success message
        """
        logger.info(f"[servers_instance_full_reset] Server full reset request id={pk}")
        try:
            server = self.get_object()
            delete_data = request.data.get("delete_data", False)

            full_reset_server_task.delay(server.pk, delete_data=delete_data, user_id=request.user.id)

            msg = "Serveur remis à zéro et relancé"
            if delete_data:
                msg += " (données supprimées)"

            ServerStatus.objects.create(
                server=server,
                status=ServerInstance.CREATING,
                message=msg,
                triggered_by=request.user,
            )
            logger.info(f"[servers_instance_full_reset] Server full reset initiated id={pk}")

            return Response({"message": msg})
        except NotFound:
            logger.warning(f"[servers_instance_start] Server not found id={pk}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
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
        """
        Stop a server instance.

        This method initiates the server shutdown process asynchronously.
        The server status will be updated to STOPPING, and a background task
        will handle the actual Docker container shutdown.

        Returns:
            Response with success message or error if server is already stopped
        """
        logger.info(f"[servers_instance_stop] Server stop request id={pk}")
        try:
            server = self.get_object()

            if server.status == ServerInstance.STOPPED:
                logger.warning(f"[servers_instance_stop] Server already stopped id={pk}")
                return Response(
                    {"error": "Le serveur est déjà arrêté"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            stop_server_task.delay(server.pk, request.user.id)

            ServerStatus.objects.create(
                server=server,
                status=ServerInstance.STOPPING,
                message="Arrêt du serveur demandé",
                triggered_by=request.user,
            )
            logger.info(f"[servers_instance_stop] Server stop initiated id={pk}")

            return Response({"message": "Arrêt du serveur en cours"})
        except NotFound:
            logger.warning(f"[servers_instance_stop] Server not found id={pk}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
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
        """
        Restart a server instance.

        This method initiates the server restart process asynchronously.
        The server will be stopped and then started again.

        Returns:
            Response with success message
        """
        logger.info(f"[servers_instance_restart] Server restart request id={pk}")
        try:
            server = self.get_object()

            restart_server_task.delay(server.pk, request.user.id)

            ServerStatus.objects.create(
                server=server,
                status=ServerInstance.STARTING,
                message="Redémarrage du serveur demandé",
                triggered_by=request.user,
            )
            logger.info(f"[servers_instance_restart] Server restart initiated id={pk}")

            return Response({"message": "Redémarrage du serveur en cours"})
        except NotFound:
            logger.warning(f"[servers_instance_restart] Server not found id={pk}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
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
        """
        Update the server to the latest or specified game version.

        This method updates the server's Docker image and configuration to match
        a new game version. By default, the server must be stopped before updating,
        unless the 'force' parameter is set to True.

        Request Body:
            force (bool, optional): If True, allows update even if server is running

        Returns:
            Response with success message or error if server must be stopped
        """
        force = request.data.get("force", False)
        logger.info(f"[servers_instance_update_server] Server update request id={pk} force={force}")
        try:
            server = self.get_object()

            if server.is_running and not force:
                logger.warning(f"[servers_instance_update_server] Server must be stopped to update id={pk}")
                return Response(
                    {"error": "Le serveur doit être arrêté pour être mis à jour"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            update_server_task(server.pk)

            ServerStatus.objects.create(
                server=server,
                status=ServerInstance.UPDATING,
                message="Mise à jour du serveur demandée.",
                triggered_by=request.user,
            )
            logger.info(f"[servers_instance_update_server] Server update initiated id={pk}")

            return Response({"message": "Mise à jour du serveur en cours"})
        except NotFound:
            logger.warning(f"[servers_instance_update_server] Server not found id={pk}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
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
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
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
            # TODO: implement socker to stream logs
            return Response(
                {
                    "logs": "Logs Docker à implémenter",
                    "container_id": server.container_id,
                }
            )
        except NotFound:
            logger.warning(f"[servers_instance_logs] Server not found id={pk}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[servers_instance_logs] Error getting logs id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la récupération des logs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get", "post"])
    def roles(self, request, pk=None):
        """
        List or add/delete roles for a server instance.

        GET: Return all roles configured for the server
        POST: Add a new role with a specific permission level.
              Only the owner can add roles.
              Only the owner can delete roles.


        Returns:
            GET: List of roles with status 200
            POST: Role data created with status 201
        """
        try:
            server = self.get_object()

            if server.owner != request.user and not request.user.is_admin:
                return Response(
                    {"error": "Seul le propriétaire peut gérer les rôles"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if request.method == "GET":
                logger.info(f"[servers_instance_roles] Get server roles request id={pk}")
                roles = server.roles.all()
                serializer = ServerRoleSerializer(roles, many=True)
                return Response(serializer.data)
            elif request.method == "POST":
                action = request.data.get("action")
                if action == "add":
                    logger.info(f"[servers_instance_roles] Add server role request id={pk}")
                    serializer = ServerRoleSerializer(
                        data=request.data,
                        context={"request": request, "server": server},
                    )
                    serializer.is_valid(raise_exception=True)
                    serializer.save(server=server, added_by=request.user)
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                elif action == "delete":
                    logger.info(f"[servers_instance_roles] Delete server role request id={pk}")
                    role = server.roles.get(id=request.data.get("id"))
                    role.delete()
                    return Response(status=status.HTTP_204_NO_CONTENT)
                else:
                    return Response({"error": "Action invalide"}, status=status.HTTP_400_BAD_REQUEST)

        except NotFound:
            logger.warning(f"[servers_instance_roles] Server not found id={pk}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except DRFValidationError as e:
            logger.warning(f"[servers_instance_roles] Validation error id={pk} errors={e.detail}")
            raise
        except IntegrityError as e:
            logger.error(f"[servers_instance_roles] Integrity error id={pk} error={str(e)}")
            return Response(
                {"error": "Cet utilisateur a déjà un rôle sur ce serveur"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"[servers_instance_roles] Unexpected error id={pk} error={str(e)}")
            raise

    @action(detail=True, methods=["get"])
    def metrics(self, request, pk=None):
        """
        Get server metrics.

        Query parameters:
            start_date (ISO format, optional): Start date to filter metrics
            end_date (ISO format, optional): End date to filter metrics
            limit (int, optional): Maximum number of results (default: 20)

        Returns:
            List of metrics with timestamp, cpu_usage, memory_usage, memory_percent
        """
        from django.utils.dateparse import parse_datetime

        try:
            server = self.get_object()
            logger.info(f"[servers_instance_metrics] Get server metrics request id={pk}")

            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")
            limit = request.query_params.get("limit", 20)

            try:
                limit = int(limit)
                if limit < 1 or limit > 10000:
                    limit = 20
            except (ValueError, TypeError):
                limit = 20

            queryset = ServerMetrics.objects.filter(server=server)

            if start_date_str:
                try:
                    start_date = parse_datetime(start_date_str)
                    if start_date:
                        queryset = queryset.filter(created_at__gte=start_date)
                except (ValueError, TypeError):
                    logger.warning(f"[servers_instance_metrics] Invalid start_date format: {start_date_str}")

            if end_date_str:
                try:
                    end_date = parse_datetime(end_date_str)
                    if end_date:
                        queryset = queryset.filter(created_at__lte=end_date)
                except (ValueError, TypeError):
                    logger.warning(f"[servers_instance_metrics] Invalid end_date format: {end_date_str}")

            queryset = queryset.order_by("created_at")

            metrics = queryset[:limit]

            serializer = ServerMetricsSerializer(metrics, many=True)
            logger.info(f"[servers_instance_metrics] Retrieved {len(serializer.data)} metrics for server id={pk}")

            return Response(serializer.data)

        except NotFound:
            logger.warning(f"[servers_instance_metrics] Server not found id={pk}")
            return Response({"error": "Serveur non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[servers_instance_metrics] Error retrieving metrics id={pk} error={str(e)}")
            return Response(
                {"error": "Erreur lors de la récupération des métriques"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
