from django.contrib import admin

from games.models import Game, GameConfiguration, GameMod, GameVersion


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "docker_image", "default_port", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "slug", "docker_image"]
    prepopulated_fields = {"slug": ("name",)}

    fieldsets = [
        ("Informations générales", {"fields": ("name", "slug", "description", "icon")}),
        ("Configuration Docker", {"fields": ("docker_image", "default_port")}),
        ("Documentation", {"fields": ("documentation_url",)}),
        ("Statut", {"fields": ("is_active",)}),
    ]


@admin.register(GameVersion)
class GameVersionAdmin(admin.ModelAdmin):
    list_display = ["game", "version", "release_date", "is_stable", "is_recommended"]
    list_filter = ["game", "is_stable", "is_recommended", "release_date"]
    search_fields = ["game__name", "version"]
    date_hierarchy = "release_date"

    fieldsets = [
        ("Identification", {"fields": ("game", "version")}),
        ("Détails", {"fields": ("release_date", "is_stable", "is_recommended")}),
        ("Changelog", {"fields": ("changelog",), "classes": ("collapse",)}),
    ]


@admin.register(GameMod)
class GameModAdmin(admin.ModelAdmin):
    list_display = ["name", "game", "mod_type", "version", "author", "is_active"]
    list_filter = ["game", "mod_type", "is_active"]
    search_fields = ["name", "slug", "author"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["compatible_game_versions"]

    fieldsets = [
        ("Informations générales", {"fields": ("game", "name", "slug", "description")}),
        ("Type et version", {"fields": ("mod_type", "version", "author")}),
        ("Téléchargement", {"fields": ("download_url", "file_name")}),
        ("Compatibilité", {"fields": ("compatible_game_versions",)}),
        ("Liens", {"fields": ("website",)}),
        ("Statut", {"fields": ("is_active",)}),
    ]


@admin.register(GameConfiguration)
class GameConfigurationAdmin(admin.ModelAdmin):
    list_display = ["name", "game", "is_default", "created_at"]
    list_filter = ["game", "is_default", "created_at"]
    search_fields = ["name", "game__name"]

    fieldsets = [
        ("Identification", {"fields": ("game", "name", "description")}),
        ("Configuration", {"fields": ("config_data", "is_default")}),
    ]
