from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Utilisateur étendu avec des informations supplémentaires"""

    ROLE_CHOICES = [
        ("user", "Utilisateur"),
        ("admin", "Administrateur"),
    ]

    role = models.CharField(
        max_length=10, choices=ROLE_CHOICES, default="user", verbose_name="Rôle"
    )
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
    """Profil utilisateur avec préférences"""

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
