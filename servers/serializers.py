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

    def validate(self, data):
        if data["game_version"].game != data["game"]:
            raise serializers.ValidationError("Game version and game do not match")

        port = data.get("port")
        additional_ports = data.get("additional_ports", {})

        if port:
            is_available, conflicting_server, conflicting_port = ServerInstance.is_port_available(
                port=port, additional_ports=additional_ports
            )

            if not is_available:
                raise serializers.ValidationError(
                    {
                        "port": f"Le port {conflicting_port} est déjà utilisé par le serveur '{conflicting_server.name}' "
                        f"(ID: {conflicting_server.id})"
                    }
                )

        configuration_data = data.get("configuration", {})
        memory_limit = configuration_data.get("memory_limit", "2g")
        cpu_limit = configuration_data.get("cpu_limit", 2.0)
        force = data.get("force", False)

        is_available, error_message = ServerInstance.check_resources_available(
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            force=force,
        )

        if not is_available:
            raise serializers.ValidationError({"resources": error_message})

        return data

    def create(self, validated_data):
        validated_data.pop("force", None)
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
            "additional_ports",
            "status",
            "configuration",
        ]

    def validate(self, data):
        port = data.get("port")
        additional_ports = data.get("additional_ports")

        if port is not None:
            is_available, conflicting_server, conflicting_port = ServerInstance.is_port_available(
                port=port,
                additional_ports=additional_ports,
                exclude_server_id=self.instance.id if self.instance else None,
            )

            if not is_available:
                raise serializers.ValidationError(
                    {
                        "port": f"Le port {conflicting_port} est déjà utilisé par le serveur '{conflicting_server.name}' "
                        f"(ID: {conflicting_server.id})"
                    }
                )

        return data

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
