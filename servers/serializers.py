from rest_framework import serializers

from games.serializers import GameSerializer, GameVersionSerializer
from servers.models import (
    ServerConfiguration,
    ServerInstance,
    ServerMetrics,
    ServerPlayer,
    ServerStatus,
)


class ServerConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerConfiguration
        fields = [
            "config_data",
            "environment_variables",
            "docker_volumes",
            "memory_limit",
            "cpu_limit",
            "custom_startup_command",
        ]

    def validate_docker_volumes(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Docker volumes must be a dict")
        # if "data" not in value:
        #     raise serializers.ValidationError("At least data folder need mapping")
        return value


class ServerPlayerSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ServerPlayer
        fields = [
            "id",
            "user",
            "username",
            "minecraft_username",
            "minecraft_uuid",
            "permission_level",
            "is_banned",
            "ban_reason",
            "added_at",
            "last_seen",
        ]
        read_only_fields = ["id", "added_at", "last_seen"]


class ServerStatusSerializer(serializers.ModelSerializer):
    triggered_by_username = serializers.CharField(source="triggered_by.username", read_only=True)

    class Meta:
        model = ServerStatus
        fields = [
            "id",
            "status",
            "message",
            "triggered_by",
            "triggered_by_username",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ServerInstanceListSerializer(serializers.ModelSerializer):
    game_name = serializers.CharField(source="game.name", read_only=True)
    game_icon = serializers.ImageField(source="game.icon", read_only=True)
    version = serializers.CharField(source="game_version.version", read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = ServerInstance
        fields = [
            "id",
            "name",
            "game_name",
            "game_icon",
            "version",
            "owner_username",
            "status",
            "port",
            "max_players",
            "is_public",
            "is_running",
            "created_at",
        ]
        read_only_fields = ["id", "is_running", "created_at"]


class ServerInstanceDetailSerializer(serializers.ModelSerializer):
    game = GameSerializer()
    game_version = GameVersionSerializer()
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    configuration = ServerConfigurationSerializer()
    players = ServerPlayerSerializer(many=True, read_only=True)
    latest_status = serializers.SerializerMethodField()

    class Meta:
        model = ServerInstance
        fields = [
            "id",
            "name",
            "game",
            "game_version",
            "owner",
            "owner_username",
            "description",
            "status",
            "container_id",
            "port",
            "max_players",
            "auto_start",
            "auto_update",
            "backup_enabled",
            "is_public",
            "is_running",
            "configuration",
            "players",
            "latest_status",
            "created_at",
            "updated_at",
            "last_started_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "status",
            "container_id",
            "is_running",
            "created_at",
            "updated_at",
            "last_started_at",
        ]

    def get_latest_status(self, obj):
        latest = obj.status_history.first()
        if latest:
            return ServerStatusSerializer(latest).data
        return None

    def validate(self, data):
        if data["game_version"].game != data["game"]:
            raise serializers.ValidationError("Game version and game do not match")
        return data

    def create(self, validated_data):
        configuration_data = validated_data.pop("configuration", None)
        owner = self.context["request"].user
        default_configuration = {
            "config_data": {},
            "environment_variables": {},
            "docker_volumes": {},
            "memory_limit": "2g",
            "cpu_limit": 2.0,
            "custom_startup_command": "",
        }

        server = ServerInstance.objects.create(owner=owner, **validated_data)
        if not configuration_data or not ServerConfigurationSerializer(data=configuration_data).is_valid():
            server.configuration = ServerConfiguration.objects.create(server=server, **default_configuration)
        else:
            server.configuration = ServerConfiguration.objects.create(server=server, **configuration_data)
        server.save()

        return server

    def update(self, instance, validated_data):
        configuration_data = validated_data.pop("configuration", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if configuration_data and hasattr(instance, "configuration"):
            config = instance.configuration
            for attr, value in configuration_data.items():
                setattr(config, attr, value)
            config.save()

        return instance


class ServerInstanceCreateSerializer(serializers.ModelSerializer):
    configuration = ServerConfigurationSerializer(required=False)

    class Meta:
        model = ServerInstance
        fields = [
            "id",
            "name",
            "game",
            "game_version",
            "description",
            "port",
            "additional_ports",
            "max_players",
            "auto_start",
            "auto_update",
            "backup_enabled",
            "is_public",
            "configuration",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        if data["game_version"].game != data["game"]:
            raise serializers.ValidationError("Game version and game do not match")
        return data

    def create(self, validated_data):
        configuration_data = validated_data.pop("configuration", None)
        owner = self.context["request"].user
        default_configuration = {
            "config_data": {},
            "environment_variables": {},
            "docker_volumes": {},
            "memory_limit": "2g",
            "cpu_limit": 2.0,
            "custom_startup_command": "",
        }

        server = ServerInstance.objects.create(owner=owner, **validated_data)
        if not configuration_data or not ServerConfigurationSerializer(data=configuration_data).is_valid():
            server.configuration = ServerConfiguration.objects.create(server=server, **default_configuration)
        else:
            server.configuration = ServerConfiguration.objects.create(server=server, **configuration_data)
        server.save()

        return server


class ServerInstanceUpdateSerializer(serializers.ModelSerializer):
    configuration = ServerConfigurationSerializer(required=False)

    class Meta:
        model = ServerInstance
        fields = [
            "name",
            "description",
            "max_players",
            "auto_start",
            "auto_update",
            "backup_enabled",
            "is_public",
            "port",
            "status",
            "configuration",
        ]

    def update(self, instance, validated_data):
        configuration_data = validated_data.pop("configuration", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if configuration_data and hasattr(instance, "configuration"):
            config = instance.configuration
            for attr, value in configuration_data.items():
                setattr(config, attr, value)
            config.save()

        return instance


class ServerMetricsSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = ServerMetrics
        fields = [
            "id",
            "timestamp",
            "cpu_usage",
            "memory_usage",
            "memory_percent",
            "players_online",
            "tps",
            "uptime_seconds",
        ]
        read_only_fields = ["id", "timestamp"]
