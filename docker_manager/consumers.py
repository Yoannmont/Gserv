"""
WebSocket consumers for Docker container management
"""

import asyncio
import json
import logging
from typing import Any

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from docker_manager.services.docker_service import DockerServiceError, get_docker_service
from servers.models import ServerInstance

logger = logging.getLogger(__name__)
User = get_user_model()


class ContainerLogsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for streaming container logs in real-time

    Connection URL: ws://<host>/ws/containers/<container_id>/logs/

    Query parameters:
        - token: JWT access token for authentication
        - tail: Number of initial log lines (default: 100)
        - timestamps: Include timestamps (default: true)

    Messages sent to client:
        - type: "log" - Log line from container
        - type: "error" - Error message
        - type: "status" - Connection status update

    Messages from client:
        - {"action": "pause"} - Pause log streaming
        - {"action": "resume"} - Resume log streaming
        - {"action": "clear"} - Clear logs on frontend (no backend action)
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.container_id: str = ""
        self.server_id: int | None = None
        self.user: User | None = None
        self.streaming_task: asyncio.Task | None = None
        self.is_streaming: bool = False
        self.tail: int = 100
        self.timestamps: bool = True

    async def connect(self) -> None:
        """Handle WebSocket connection"""
        self.container_id = self.scope["url_route"]["kwargs"]["container_id"]

        # Parse query parameters
        query_string = self.scope.get("query_string", b"").decode()
        query_params = self._parse_query_string(query_string)

        # Authenticate user
        token = query_params.get("token")
        if not token:
            await self.close(code=4001)
            return

        self.user = await self._authenticate_token(token)
        if not self.user:
            await self.close(code=4001)
            return

        # Verify access to the container
        has_access = await self._verify_container_access()
        if not has_access:
            await self.close(code=4003)
            return

        # Parse streaming options
        self.tail = int(query_params.get("tail", 100))
        self.timestamps = query_params.get("timestamps", "true").lower() == "true"

        # Accept the connection
        await self.accept()

        logger.info(f"[ContainerLogsConsumer] User {self.user.username} connected to logs for container {self.container_id}")

        # Send connection status
        await self.send_status("connected", f"Connecté aux logs du conteneur {self.container_id[:12]}")

        # Start streaming logs
        await self.start_streaming()

    async def disconnect(self, close_code: int) -> None:
        """Handle WebSocket disconnection"""
        await self.stop_streaming()
        logger.info(
            f"[ContainerLogsConsumer] User {getattr(self.user, 'username', 'unknown')} "
            f"disconnected from container {self.container_id} (code: {close_code})"
        )

    async def receive(self, text_data: str) -> None:
        """Handle messages from the client"""
        try:
            data = json.loads(text_data)
            action = data.get("action")

            if action == "pause":
                await self.stop_streaming()
                await self.send_status("paused", "Streaming en pause")

            elif action == "resume":
                await self.start_streaming()
                await self.send_status("resumed", "Streaming repris")

            elif action == "clear":
                # Just acknowledge, frontend handles clearing
                await self.send_status("cleared", "Logs effacés")

            elif action == "refresh":
                # Stop current stream and restart with fresh logs
                await self.stop_streaming()
                await self.start_streaming()
                await self.send_status("refreshed", "Logs rafraîchis")

            else:
                await self.send_error(f"Action inconnue: {action}")

        except json.JSONDecodeError:
            await self.send_error("Format de message invalide")

    async def start_streaming(self) -> None:
        """Start the log streaming task"""
        if self.is_streaming:
            return

        self.is_streaming = True
        self.streaming_task = asyncio.create_task(self._stream_logs())

    async def stop_streaming(self) -> None:
        """Stop the log streaming task"""
        self.is_streaming = False
        if self.streaming_task:
            self.streaming_task.cancel()
            try:
                await self.streaming_task
            except asyncio.CancelledError:
                pass
            self.streaming_task = None

    async def _stream_logs(self) -> None:
        """Stream logs from the Docker container"""
        try:
            docker_service = get_docker_service()

            # Run the streaming in a thread pool to avoid blocking
            log_generator = await sync_to_async(
                lambda: docker_service.stream_container_logs(
                    self.container_id,
                    tail=self.tail,
                    timestamps=self.timestamps,
                )
            )()

            async for log_line in self._async_generator(log_generator):
                if not self.is_streaming:
                    break

                await self.send_log(log_line)

        except DockerServiceError as e:
            await self.send_error(str(e))
            await self.close(code=4004)

        except asyncio.CancelledError:
            # Normal cancellation, don't send error
            raise

        except Exception as e:
            logger.exception(f"[ContainerLogsConsumer] Unexpected error streaming logs: {e}")
            await self.send_error(f"Erreur inattendue: {e}")

    async def _async_generator(self, sync_generator):
        """Convert a synchronous generator to an async one"""
        loop = asyncio.get_event_loop()

        def get_next():
            try:
                return next(sync_generator), False
            except StopIteration:
                return None, True

        while True:
            item, done = await loop.run_in_executor(None, get_next)
            if done:
                break
            yield item

    async def send_log(self, log_line: str) -> None:
        """Send a log line to the client"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "log",
                    "data": log_line.strip(),
                }
            )
        )

    async def send_error(self, message: str) -> None:
        """Send an error message to the client"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "error",
                    "message": message,
                }
            )
        )

    async def send_status(self, status: str, message: str) -> None:
        """Send a status update to the client"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "status",
                    "status": status,
                    "message": message,
                }
            )
        )

    def _parse_query_string(self, query_string: str) -> dict[str, str]:
        """Parse query string into a dictionary"""
        params = {}
        if query_string:
            for param in query_string.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value
        return params

    @database_sync_to_async
    def _authenticate_token(self, token: str) -> User | None:
        """Authenticate JWT token and return user"""
        try:
            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            return User.objects.get(id=user_id)
        except Exception as e:
            logger.warning(f"[ContainerLogsConsumer] Token authentication failed: {e}")
            return None

    @database_sync_to_async
    def _verify_container_access(self) -> bool:
        """Verify that the user has access to the container"""
        try:
            # Find server by container_id
            server = ServerInstance.objects.filter(container_id=self.container_id).first()

            if not server:
                logger.warning(f"[ContainerLogsConsumer] Container {self.container_id} not found in database")
                return False

            self.server_id = server.id

            # Check if user is owner or staff
            if self.user.is_staff or server.owner_id == self.user.id:
                return True

            # Check if user has player access with admin permission
            has_admin_access = server.players.filter(user=self.user, permission_level="admin", is_banned=False).exists()

            return has_admin_access

        except Exception as e:
            logger.exception(f"[ContainerLogsConsumer] Error verifying container access: {e}")
            return False


class ContainerStatsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for streaming container stats in real-time

    Connection URL: ws://<host>/ws/containers/<container_id>/stats/

    Query parameters:
        - token: JWT access token for authentication
        - interval: Update interval in seconds (default: 2)
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.container_id: str = ""
        self.user: User | None = None
        self.streaming_task: asyncio.Task | None = None
        self.is_streaming: bool = False
        self.interval: int = 2

    async def connect(self) -> None:
        """Handle WebSocket connection"""
        self.container_id = self.scope["url_route"]["kwargs"]["container_id"]

        # Parse query parameters
        query_string = self.scope.get("query_string", b"").decode()
        query_params = self._parse_query_string(query_string)

        # Authenticate user
        token = query_params.get("token")
        if not token:
            await self.close(code=4001)
            return

        self.user = await self._authenticate_token(token)
        if not self.user:
            await self.close(code=4001)
            return

        # Verify access to the container
        has_access = await self._verify_container_access()
        if not has_access:
            await self.close(code=4003)
            return

        # Parse options
        self.interval = max(1, int(query_params.get("interval", 2)))

        # Accept the connection
        await self.accept()

        logger.info(f"[ContainerStatsConsumer] User {self.user.username} connected to stats for container {self.container_id}")

        # Start streaming stats
        await self.start_streaming()

    async def disconnect(self, close_code: int) -> None:
        """Handle WebSocket disconnection"""
        await self.stop_streaming()

    async def receive(self, text_data: str) -> None:
        """Handle messages from the client"""
        try:
            data = json.loads(text_data)
            action = data.get("action")

            if action == "pause":
                await self.stop_streaming()
            elif action == "resume":
                await self.start_streaming()

        except json.JSONDecodeError:
            pass

    async def start_streaming(self) -> None:
        """Start the stats streaming task"""
        if self.is_streaming:
            return

        self.is_streaming = True
        self.streaming_task = asyncio.create_task(self._stream_stats())

    async def stop_streaming(self) -> None:
        """Stop the stats streaming task"""
        self.is_streaming = False
        if self.streaming_task:
            self.streaming_task.cancel()
            try:
                await self.streaming_task
            except asyncio.CancelledError:
                pass
            self.streaming_task = None

    async def _stream_stats(self) -> None:
        """Stream stats from the Docker container"""
        try:
            while self.is_streaming:
                stats = await self._get_container_stats()
                if stats:
                    await self.send(text_data=json.dumps({"type": "stats", "data": stats}))
                await asyncio.sleep(self.interval)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"[ContainerStatsConsumer] Error streaming stats: {e}")
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    @database_sync_to_async
    def _get_container_stats(self) -> dict | None:
        """Get container stats"""
        try:
            docker_service = get_docker_service()
            return docker_service.get_container_stats(self.container_id)
        except DockerServiceError:
            return None

    def _parse_query_string(self, query_string: str) -> dict[str, str]:
        """Parse query string into a dictionary"""
        params = {}
        if query_string:
            for param in query_string.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value
        return params

    @database_sync_to_async
    def _authenticate_token(self, token: str) -> User | None:
        """Authenticate JWT token and return user"""
        try:
            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            return User.objects.get(id=user_id)
        except Exception:
            return None

    @database_sync_to_async
    def _verify_container_access(self) -> bool:
        """Verify that the user has access to the container"""
        try:
            server = ServerInstance.objects.filter(container_id=self.container_id).first()

            if not server:
                return False

            if self.user.is_staff or server.owner_id == self.user.id:
                return True

            return server.players.filter(user=self.user, permission_level="admin", is_banned=False).exists()

        except Exception:
            return False
