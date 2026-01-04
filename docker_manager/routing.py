"""
WebSocket URL routing for docker_manager
"""

from django.urls import re_path

from docker_manager.consumers import ContainerLogsConsumer, ContainerStatsConsumer

websocket_urlpatterns = [
    re_path(
        r"gserv/ws/containers/(?P<container_id>[a-f0-9]+)/logs/$",
        ContainerLogsConsumer.as_asgi(),
    ),
    re_path(
        r"gserv/ws/containers/(?P<container_id>[a-f0-9]+)/stats/$",
        ContainerStatsConsumer.as_asgi(),
    ),
]
