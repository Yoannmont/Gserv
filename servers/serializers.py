from django.contrib.auth import get_user_model
from rest_framework import serializers

from games.serializers import GameSerializer, GameVersionSerializer
from servers.models import (
    ServerConfiguration,
    ServerInstance,
    ServerMetrics,
    ServerRole,
    ServerStatus,
)


class ServerConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerConfiguration
        fields = [
            "environment_variables",
            "docker_volumes",
            "memory_limit",
            "cpu_limit",
            "custom_startup_command",
        ]

    def validate_docker_volumes(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Docker volumes must be a dict")

        return value


class ServerRoleSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(),
        required=False,
        allow_null=True,
        help_text="ID de l'utilisateur. Peut être omis si 'username' est fourni.",
    )
    username_input = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Nom d'utilisateur pour créer le rôle. Alternative à 'user'.",
    )
    added_by_username = serializers.CharField(source="added_by.username", read_only=True)

    class Meta:
        model = ServerRole
        fields = [
            "id",
            "user",
            "username",
            "username_input",
            "role",
            "can_view",
            "can_edit",
            "can_control",
            "can_delete",
            "added_at",
            "added_by_username",
        ]
        extra_kwargs = {
            "server": {"required": False, "read_only": False},
            "added_by": {"required": False, "read_only": False},
        }
        read_only_fields = [
            "id",
            "can_view",
            "can_edit",
            "can_control",
            "can_delete",
            "added_at",
            "username",
        ]

    def validate(self, data):
        if self.instance is None:
            user_provided = data.get("user") is not None
            username_provided = data.get("username_input") and data.get("username_input").strip()

            if not user_provided and not username_provided:
                raise serializers.ValidationError({"user": "Soit 'user' soit 'username_input' doit être fourni"})

        return data

    def update(self, instance, validated_data):
        request = self.context.get("request")
        server = self.context.get("server")

        instance.role = validated_data.get("role", instance.role)
        instance.server = server
        instance.added_by = request.user
        instance.save()

        return instance

    def create(self, validated_data):
        username_input = validated_data.pop("username_input", None)

        request = self.context.get("request")
        server = self.context.get("server")

        if username_input and username_input.strip() and not validated_data.get("user"):
            try:
                user = get_user_model().objects.get(username=username_input.strip())
                if server.roles.filter(user=user).exists():
                    raise serializers.ValidationError({"user": "Cet utilisateur a déjà un rôle sur ce serveur."})
                validated_data["user"] = user
            except get_user_model().DoesNotExist:
                raise serializers.ValidationError({"username_input": f"Utilisateur '{username_input}' introuvable"})

        if validated_data.get("user"):
            if server.roles.filter(user=validated_data["user"]).exists():
                raise serializers.ValidationError({"user": "Cet utilisateur a déjà un rôle sur ce serveur."})

        validated_data["server"] = server
        validated_data["added_by"] = request.user

        return super().create(validated_data)


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
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = ServerInstance
        fields = [
            "id",
            "name",
            "game_name",
            "game_icon",
            "owner_username",
            "status",
            "is_public",
            "created_at",
        ]


class ServerInstanceDetailSerializer(serializers.ModelSerializer):
    game = GameSerializer()
    game_version = GameVersionSerializer()
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    configuration = ServerConfigurationSerializer()
    user_role = serializers.SerializerMethodField()

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
            "additional_ports",
            "max_players",
            "auto_start",
            "auto_update",
            "backup_enabled",
            "is_public",
            "configuration",
            "created_at",
            "updated_at",
            "last_started_at",
            "user_role",
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
            "user_role",
        ]

    def get_user_role(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            try:
                return obj.roles.get(user=request.user).role
            except ServerRole.DoesNotExist:
                return None
        return None


class ServerInstanceSerializer(serializers.ModelSerializer):
    configuration = ServerConfigurationSerializer(required=False)
    force = serializers.BooleanField(write_only=True, required=False, default=False)

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
            "force",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "game": {"required": False},
            "game_version": {"required": False},
        }

    def validate(self, data):
        server_instance = self.instance
        game = data.get("game") or (server_instance.game if server_instance else None)
        game_version = data.get("game_version") or (server_instance.game_version if server_instance else None)
        if server_instance is None and (not game or not game_version):
            raise serializers.ValidationError({"game": "Champ requis.", "game_version": "Champ requis."})

        if game and game_version and game_version.game_id != game.id:
            raise serializers.ValidationError("Game version and game do not match")

        # Checking if ports are available
        port_in_payload = "port" in data
        additional_ports_in_payload = "additional_ports" in data
        port = data.get("port", getattr(server_instance, "port", None))
        additional_ports = data.get("additional_ports", getattr(server_instance, "additional_ports", {})) or {}

        if port_in_payload or additional_ports_in_payload:
            is_available, conflicting_server, conflicting_port = ServerInstance.is_port_available(
                port=port,
                additional_ports=additional_ports,
                exclude_server_id=server_instance.id if server_instance else None,
            )

            if not is_available:
                raise serializers.ValidationError(
                    {
                        "port": f"Le port {conflicting_port} est déjà utilisé par le serveur '{conflicting_server.name}' "
                        f"(ID: {conflicting_server.id})"
                    }
                )

        payload_configuration = data.get("configuration")
        force = data.get("force", False)

        # Computing final configuration (defaults game -> existing config -> payload)
        default_game_configuration = ServerInstance.get_default_configuration_for_game(game)
        existing_server_configuration = {}
        if server_instance and hasattr(server_instance, "configuration"):
            try:
                existing_server_configuration = {
                    "environment_variables": server_instance.configuration.environment_variables,
                    "docker_volumes": server_instance.configuration.docker_volumes,
                    "memory_limit": server_instance.configuration.memory_limit,
                    "cpu_limit": server_instance.configuration.cpu_limit,
                    "custom_startup_command": server_instance.configuration.custom_startup_command,
                }
            except Exception:
                pass

        payload_validated = {}
        if payload_configuration is not None:
            cfg_ser = ServerConfigurationSerializer(data=payload_configuration, partial=True)
            cfg_ser.is_valid(raise_exception=True)
            payload_validated = cfg_ser.validated_data

        final_configuration = default_game_configuration | existing_server_configuration | payload_validated
        memory_limit = final_configuration["memory_limit"]
        cpu_limit = final_configuration["cpu_limit"]

        is_available, error_message = ServerInstance.check_resources_available(
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            exclude_server_id=server_instance.id if server_instance else None,
            force=force,
        )

        if not is_available:
            raise serializers.ValidationError({"resources": error_message})

        data["configuration"] = final_configuration

        return data

    def create(self, validated_data):
        validated_data.pop("force", None)
        configuration_data = validated_data.pop("configuration")
        owner = self.context["request"].user

        server_instance = ServerInstance.objects.create(owner=owner, **validated_data)
        ServerConfiguration.objects.create(server=server_instance, **configuration_data)

        return server_instance

    def update(self, instance, validated_data):
        validated_data.pop("force", None)
        configuration_data = validated_data.pop("configuration")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if hasattr(instance, "configuration"):
            config = instance.configuration
            for attr, value in configuration_data.items():
                setattr(config, attr, value)
            config.save()
        else:
            ServerConfiguration.objects.create(server=instance, **configuration_data)

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
