from django.contrib import admin

from games.models import Game, GameConfiguration, GameVersion


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "docker_image",
        "default_port",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "slug", "docker_image"]
    prepopulated_fields = {"slug": ("name",)}

    fieldsets = [
        ("Informations générales", {"fields": ("name", "slug", "description", "icon")}),
        (
            "Configuration Docker",
            {
                "fields": (
                    "docker_image",
                    "default_port",
                    "additional_ports",
                    "health_check_command",
                )
            },
        ),
        ("Documentation", {"fields": ("documentation_url",)}),
        ("Statut", {"fields": ("is_active",)}),
    ]


@admin.register(GameVersion)
class GameVersionAdmin(admin.ModelAdmin):
    list_display = [
        "game",
        "version",
        "release_date",
        "docker_tag",
    ]
    list_filter = ["game", "release_date"]
    search_fields = ["game__name", "version"]
    date_hierarchy = "release_date"

    fieldsets = [
        ("Identification", {"fields": ("game", "version", "docker_tag")}),
        ("Détails", {"fields": ("release_date",)}),
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
