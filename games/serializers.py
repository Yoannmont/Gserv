from rest_framework import serializers

from games.models import Game, GameConfiguration, GameMod, GameVersion


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


class GameModSerializer(serializers.ModelSerializer):
    game_name = serializers.CharField(source="game.name", read_only=True)
    compatible_versions = serializers.SerializerMethodField()

    class Meta:
        model = GameMod
        fields = [
            "id",
            "game",
            "game_name",
            "name",
            "slug",
            "description",
            "mod_type",
            "version",
            "download_url",
            "file_name",
            "author",
            "website",
            "is_active",
            "compatible_versions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_compatible_versions(self, obj):
        versions = obj.compatible_game_versions.all()
        return [v.version for v in versions]


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


class GameModCreateSerializer(serializers.ModelSerializer):
    compatible_game_versions = serializers.PrimaryKeyRelatedField(many=True, queryset=GameVersion.objects.all())

    class Meta:
        model = GameMod
        fields = [
            "game",
            "name",
            "slug",
            "description",
            "mod_type",
            "version",
            "download_url",
            "file_name",
            "author",
            "website",
            "compatible_game_versions",
        ]
