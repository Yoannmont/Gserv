from django.contrib import admin

from servers.models import (
    ServerBackup,
    ServerConfiguration,
    ServerInstance,
    ServerMetrics,
    ServerRole,
    ServerStatus,
)


class ServerConfigurationInline(admin.StackedInline):
    model = ServerConfiguration
    can_delete = False
    verbose_name_plural = "Configuration"


class InstanceBackupInline(admin.TabularInline):
    model = ServerBackup
    verbose_name_plural = "Backups"
    verbose_name = "Backup"
    can_delete = False
    readonly_fields = [
        "name",
        "description",
        "mo_file_size",
        "created_at",
        "created_by",
    ]
    autocomplete_fields = ["created_by"]
    fields = ["name", "description", "mo_file_size", "created_at", "created_by"]
    list_display = ["name", "description", "file_size", "created_at", "created_by"]
    list_filter = ["created_at", "created_by"]
    search_fields = ["name", "description", "created_by__username"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def mo_file_size(self, obj):
        return f"{obj.file_size / 1024 / 1024:.2f} MB"


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
    inlines = [ServerConfigurationInline, InstanceBackupInline]

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
        (
            "Avancé",
            {
                "fields": ("custom_startup_command",),
                "classes": ("collapse",),
            },
        ),
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


@admin.register(ServerRole)
class ServerRoleAdmin(admin.ModelAdmin):
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
    readonly_fields = ["added_at", "added_by", "user"]
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


@admin.register(ServerBackup)
class ServerBackup(admin.ModelAdmin):
    list_display = ["name", "created_at", "created_by"]

    search_fields = ["name"]

    readonly_fields = ["created_at", "created_by", "mo_file_size"]
    autocomplete_fields = ["created_by"]

    def mo_file_size(self, obj):
        return f"{obj.file_size / 1024 / 1024:.2f} MB"

    fieldsets = [
        ("Serveur", {"fields": ("server",)}),
        (
            "Infos",
            {
                "fields": (
                    "name",
                    "description",
                    "file_path",
                    "mo_file_size",
                )
            },
        ),
    ]
