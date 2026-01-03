from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended user model with additional fields"""

    ROLE_CHOICES = [
        ("user", "Utilisateur"),
        ("admin", "Administrateur"),
    ]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user", verbose_name="Rôle")
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True, verbose_name="Avatar")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.username

    @property
    def is_admin(self):
        return self.role == "admin"


class UserProfile(models.Model):
    """User profile with preferences"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Utilisateur",
    )
    bio = models.TextField(blank=True, verbose_name="Biographie")
    discord_username = models.CharField(max_length=100, blank=True, verbose_name="Discord")
    notifications_enabled = models.BooleanField(default=True, verbose_name="Notifications activées")
    theme = models.CharField(
        max_length=20,
        choices=[("light", "Clair"), ("dark", "Sombre")],
        default="dark",
        verbose_name="Thème",
    )

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        return f"Profil de {self.user.username}"


class AllowedAdminIP(models.Model):
    """IP addresses allowed to access the Django admin"""

    ip_address = models.GenericIPAddressField(unique=True, verbose_name="Adresse IP", help_text="Adresse IPv4 ou IPv6")
    description = models.CharField(
        max_length=255, blank=True, verbose_name="Description", help_text="Description optionnelle (ex: Bureau principal)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")

    class Meta:
        verbose_name = "IP autorisée pour l'admin"
        verbose_name_plural = "IP autorisées pour l'admin"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ip_address} - {self.description or 'Sans description'}"
