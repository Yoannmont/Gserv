from django.contrib import admin

from servers.models import (
    ServerConfiguration,
    ServerInstance,
    ServerManager,
    ServerMetrics,
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
    list_filter = [
        "status",
        "game",
        "is_public",
        "auto_start",
        "auto_update",
        "created_at",
    ]
    search_fields = ["name", "owner__username", "description"]
    date_hierarchy = "created_at"
    inlines = [ServerConfigurationInline]

    fieldsets = [
        (
            "Informations générales",
            {"fields": ("name", "game", "game_version", "owner", "description")},
        ),
        (
            "Configuration réseau",
            {"fields": ("port", "additional_ports", "max_players")},
        ),
        ("Statut", {"fields": ("status", "container_id")}),
        (
            "Options",
            {"fields": ("auto_start", "auto_update", "backup_enabled", "is_public")},
        ),
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


@admin.register(ServerManager)
class ServerManagerAdmin(admin.ModelAdmin):
    list_display = [
        "server",
        "user",
        "role",
        "can_view",
        "can_edit",
        "can_control",
        "can_delete",
        "added_at",
        "added_by",
    ]
    list_filter = [
        "role",
        "can_view",
        "can_edit",
        "can_control",
        "can_delete",
        "added_at",
    ]
    search_fields = ["server__name", "user__username", "user__email"]
    readonly_fields = ["added_at"]
    autocomplete_fields = ["user", "added_by"]

    fieldsets = (
        (
            "Informations",
            {
                "fields": ("server", "user", "role"),
            },
        ),
        (
            "Permissions",
            {
                "fields": ("can_view", "can_edit", "can_control", "can_delete"),
                "description": "Les permissions sont automatiquement mises à jour selon le rôle",
            },
        ),
        (
            "Métadonnées",
            {
                "fields": ("added_at", "added_by"),
            },
        ),
    )


@admin.register(ServerMetrics)
class ServerMetricsAdmin(admin.ModelAdmin):
    list_display = [
        "server",
        "cpu_usage",
        "memory_usage",
        "memory_percent",
        "players_online",
        "tps",
        "uptime_seconds",
        "created_at",
    ]
    list_filter = ["created_at", "server__game"]
    search_fields = ["server__name"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at"]

    fieldsets = [
        ("Serveur", {"fields": ("server",)}),
        (
            "Métriques",
            {
                "fields": (
                    "cpu_usage",
                    "memory_usage",
                    "memory_percent",
                    "players_online",
                    "tps",
                    "uptime_seconds",
                )
            },
        ),
    ]
