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
            "is_stable",
            "is_recommended",
            "changelog",
            "created_at",
            "docker_tag",
            "game_id",
        ]
        read_only_fields = ["id", "created_at"]


class GameSerializer(serializers.ModelSerializer):
    versions_count = serializers.SerializerMethodField()
    mods_count = serializers.SerializerMethodField()
    latest_version = serializers.SerializerMethodField()

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
            "versions_count",
            "mods_count",
            "latest_version",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_versions_count(self, obj):
        return obj.versions.count()

    def get_mods_count(self, obj):
        return obj.mods.filter(is_active=True).count()

    def get_latest_version(self, obj):
        version = obj.versions.filter(is_stable=True).first()
        if version:
            return GameVersionSerializer(version).data
        return None


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
            "config_data",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
