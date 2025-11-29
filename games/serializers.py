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


class GameModSerializer(serializers.ModelSerializer):
    game_name = serializers.CharField(source="game.name", read_only=True)
    compatible_game_versions = serializers.PrimaryKeyRelatedField(many=True, queryset=GameVersion.objects.all())

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
            "compatible_game_versions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class GameModUpdateSerializer(serializers.ModelSerializer):
    compatible_game_versions = serializers.PrimaryKeyRelatedField(many=True, queryset=GameVersion.objects.all())

    class Meta:
        model = GameMod
        fields = [
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
            "compatible_game_versions",
        ]

    def update(self, instance, validated_data):
        compatible_game_versions = validated_data.pop("compatible_game_versions", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if compatible_game_versions:
            instance.compatible_game_versions.set(compatible_game_versions)
        return instance


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

    def create(self, validated_data):
        compatible_game_versions = validated_data.pop("compatible_game_versions", None)
        mod = GameMod.objects.create(**validated_data)
        if compatible_game_versions:
            for version in compatible_game_versions:
                mod.compatible_game_versions.add(version)
        return mod
