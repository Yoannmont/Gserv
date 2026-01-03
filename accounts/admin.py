from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import AllowedAdminIP, User, UserProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "role", "is_active", "created_at"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["username", "email", "first_name", "last_name"]

    fieldsets = BaseUserAdmin.fieldsets + (("Informations supplémentaires", {"fields": ("role", "avatar")}),)

    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Informations supplémentaires", {"fields": ("role",)}),)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "discord_username", "notifications_enabled", "theme"]
    list_filter = ["notifications_enabled", "theme"]
    search_fields = ["user__username", "discord_username"]

    fieldsets = [
        ("Utilisateur", {"fields": ("user",)}),
        ("Informations", {"fields": ("bio", "discord_username")}),
        ("Préférences", {"fields": ("notifications_enabled", "theme")}),
    ]


@admin.register(AllowedAdminIP)
class AllowedAdminIPAdmin(admin.ModelAdmin):
    list_display = ["ip_address", "description", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["ip_address", "description"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = [
        ("Adresse IP", {"fields": ("ip_address", "description")}),
        ("Statut", {"fields": ("is_active",)}),
        ("Dates", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    ]
