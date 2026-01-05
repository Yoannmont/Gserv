from rest_framework import serializers

from games.models import Game, GameConfiguration, GameVersion


class GameVersionSerializer(serializers.ModelSerializer):
    game_id = serializers.PrimaryKeyRelatedField(queryset=Game.objects.all(), source="game", write_only=True)

    class Meta:
        model = GameVersion
        fields = [
            "id",
            "version",
            "release_date",
            "created_at",
            "docker_tag",
            "game_id",
        ]
        read_only_fields = ["id", "created_at"]


class GameSerializer(serializers.ModelSerializer):
    def validate_default_port(self, value):
        """Validate default_port format: 'port' or 'port/protocol'"""
        import re

        port_str = str(value).strip()

        match = re.match(r"^(\d+)(?:/(tcp|udp))?$", port_str, re.IGNORECASE)

        if not match:
            try:
                int(port_str)
                return port_str
            except ValueError:
                raise serializers.ValidationError(
                    "Format invalide. Utilisez 'port' (ex: '25565') ou 'port/protocol' (ex: '25565/tcp', '25565/udp')"
                )

        port_num = int(match.group(1))
        if port_num < 1 or port_num > 65535:
            raise serializers.ValidationError("Le port doit être entre 1 et 65535")

        protocol = match.group(2)
        if protocol and protocol.lower() not in ["tcp", "udp"]:
            raise serializers.ValidationError("Le protocole doit être 'tcp' ou 'udp'")

        return port_str

    class Meta:
        model = Game
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "docker_image",
            "default_port",
            "additional_ports",
            "documentation_url",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class GameDetailSerializer(GameSerializer):
    versions = GameVersionSerializer(many=True, read_only=True)

    class Meta(GameSerializer.Meta):
        fields = GameSerializer.Meta.fields + ["versions"]


class GameConfigurationSerializer(serializers.ModelSerializer):
    game_name = serializers.CharField(source="game.name", read_only=True)

    class Meta:
        model = GameConfiguration
        fields = [
            "id",
            "game",
            "game_name",
            "name",
            "description",
            "is_default",
            "config_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
