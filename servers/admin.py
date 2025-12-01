from django.contrib import admin

from servers.models import (
    ServerConfiguration,
    ServerInstance,
    ServerMetrics,
    ServerPlayer,
    ServerStatus,
)


class ServerConfigurationInline(admin.StackedInline):
    model = ServerConfiguration
    can_delete = False
    verbose_name_plural = "Configuration"


@admin.register(ServerInstance)
class ServerInstanceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "game",
        "game_version",
        "owner",
        "status",
        "port",
        "is_public",
        "created_at",
    ]
    list_filter = ["status", "game", "is_public", "auto_start", "auto_update", "created_at"]
    search_fields = ["name", "owner__username", "description"]
    date_hierarchy = "created_at"
    inlines = [ServerConfigurationInline]

    fieldsets = [
        (
            "Informations générales",
            {"fields": ("name", "game", "game_version", "owner", "description")},
        ),
        ("Configuration réseau", {"fields": ("port", "additional_ports", "max_players")}),
        ("Statut", {"fields": ("status", "container_id")}),
        ("Options", {"fields": ("auto_start", "auto_update", "backup_enabled", "is_public")}),
        ("Dates", {"fields": ("last_started_at",), "classes": ("collapse",)}),
    ]

    readonly_fields = ["container_id", "owner"]


@admin.register(ServerConfiguration)
class ServerConfigurationAdmin(admin.ModelAdmin):
    list_display = ["server", "memory_limit", "cpu_limit", "updated_at"]
    list_filter = ["updated_at"]
    search_fields = ["server__name"]

    fieldsets = [
        ("Serveur", {"fields": ("server",)}),
        ("Ressources", {"fields": ("memory_limit", "cpu_limit")}),
        ("Docker", {"fields": ("environment_variables", "docker_volumes")}),
        ("Configuration", {"fields": ("config_data",)}),
        ("Avancé", {"fields": ("custom_startup_command",), "classes": ("collapse",)}),
    ]


@admin.register(ServerStatus)
class ServerStatusAdmin(admin.ModelAdmin):
    list_display = ["server", "status", "triggered_by", "created_at"]
    list_filter = ["status", "created_at", "server__game"]
    search_fields = ["server__name", "message"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at"]

    fieldsets = [
        ("Informations", {"fields": ("server", "status", "message", "triggered_by")}),
    ]


@admin.register(ServerPlayer)
class ServerPlayerAdmin(admin.ModelAdmin):
    list_display = [
        "minecraft_username",
        "server",
        "user",
        "permission_level",
        "is_banned",
        "last_seen",
    ]
    list_filter = ["permission_level", "is_banned", "added_at", "server__game"]
    search_fields = ["minecraft_username", "minecraft_uuid", "user__username", "server__name"]
    date_hierarchy = "added_at"

    fieldsets = [
        ("Serveur", {"fields": ("server",)}),
        ("Joueur", {"fields": ("user", "minecraft_username", "minecraft_uuid")}),
        ("Permissions", {"fields": ("permission_level",)}),
        ("Bannissement", {"fields": ("is_banned", "ban_reason"), "classes": ("collapse",)}),
        ("Statistiques", {"fields": ("last_seen",), "classes": ("collapse",)}),
    ]

    readonly_fields = ["last_seen"]


@admin.register(ServerMetrics)
class ServerMetricsAdmin(admin.ModelAdmin):
    list_display = ["server", "created_at"]
    readonly_fields = ["server", "created_at"]
