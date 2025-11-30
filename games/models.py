from django.core.validators import URLValidator
from django.db import models


class Game(models.Model):
    """Represents a game type (Minecraft, Palworld, etc.)"""

    name = models.CharField(max_length=100, unique=True, verbose_name="Nom du jeu")
    slug = models.SlugField(unique=True, verbose_name="Slug")
    description = models.TextField(verbose_name="Description")
    icon = models.ImageField(upload_to="games/icons/", null=True, blank=True, verbose_name="Icône")
    docker_image = models.CharField(max_length=255, verbose_name="Image Docker", help_text="Ex: itzg/minecraft-server")
    default_port = models.IntegerField(verbose_name="Port par défaut")
    additional_ports = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Ports additionnels",
        help_text='Liste de ports supplémentaires: [{"port": 27015, "protocol": "udp", "description": "Query port"}]',
    )
    documentation_url = models.URLField(blank=True, validators=[URLValidator()], verbose_name="URL de documentation")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Jeu"
        verbose_name_plural = "Jeux"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_all_ports(self):
        """Retourne tous les ports (défaut + additionnels)"""
        ports = [
            {
                "port": self.default_port,
                "protocol": "both",  # tcp and udp
                "description": "Port principal",
                "is_main": True,
            }
        ]

        for additional_port in self.additional_ports:
            ports.append(
                {
                    "port": additional_port.get("port"),
                    "protocol": additional_port.get("protocol", "tcp"),
                    "description": additional_port.get("description", ""),
                    "is_main": False,
                }
            )

        return ports


class GameVersion(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="versions", verbose_name="Jeu")
    version = models.CharField(max_length=50, verbose_name="Version", help_text="Ex: 1.20.4, latest")
    release_date = models.DateField(null=True, blank=True, verbose_name="Date de sortie")
    is_stable = models.BooleanField(default=True, verbose_name="Version stable")
    is_recommended = models.BooleanField(default=False, verbose_name="Version recommandée")
    changelog = models.TextField(blank=True, verbose_name="Changelog")
    created_at = models.DateTimeField(auto_now_add=True)
    docker_tag = models.CharField(max_length=40, verbose_name="Tag docker", help_text="Ex: java16")

    class Meta:
        verbose_name = "Version de jeu"
        verbose_name_plural = "Versions de jeux"
        unique_together = ["game", "version"]
        ordering = ["-release_date"]

    def __str__(self):
        return f"{self.game.name} - {self.version}"


class GameMod(models.Model):
    MOD_TYPE_CHOICES = [
        ("plugin", "Plugin"),
        ("mod", "Mod"),
        ("datapack", "Datapack"),
    ]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="mods", verbose_name="Jeu")
    name = models.CharField(max_length=100, verbose_name="Nom du mod")
    slug = models.SlugField(verbose_name="Slug")
    description = models.TextField(blank=True, verbose_name="Description")
    mod_type = models.CharField(max_length=20, choices=MOD_TYPE_CHOICES, default="mod", verbose_name="Type de mod")
    version = models.CharField(max_length=50, verbose_name="Version")
    download_url = models.URLField(validators=[URLValidator()], verbose_name="URL de téléchargement")
    file_name = models.CharField(max_length=255, verbose_name="Nom du fichier", help_text="Nom du fichier .jar ou .zip")
    compatible_game_versions = models.ManyToManyField(
        GameVersion, related_name="compatible_mods", verbose_name="Versions compatibles"
    )
    author = models.CharField(max_length=100, blank=True, verbose_name="Auteur")
    website = models.URLField(blank=True, validators=[URLValidator()], verbose_name="Site web")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mod"
        verbose_name_plural = "Mods"
        unique_together = ["game", "slug", "version"]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.version})"


class GameConfiguration(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="configurations", verbose_name="Jeu")
    name = models.CharField(max_length=100, verbose_name="Nom de la configuration")
    description = models.TextField(blank=True, verbose_name="Description")
    config_data = models.JSONField(verbose_name="Données de configuration", help_text="Configuration au format JSON")
    is_default = models.BooleanField(default=False, verbose_name="Configuration par défaut")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration de jeu"
        verbose_name_plural = "Configurations de jeux"
        ordering = ["game", "name"]

    def __str__(self):
        return f"{self.game.name} - {self.name}"


class PermissionRole(models.Model):
    """Specific permission roles for each game"""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="permission_roles", verbose_name="Jeu")
    name = models.CharField(max_length=50, verbose_name="Nom du rôle", help_text="Ex: Player, Moderator, Admin, Operator")
    slug = models.SlugField(verbose_name="Slug")
    level = models.IntegerField(
        default=0,
        verbose_name="Niveau de permission",
        help_text="Plus le nombre est élevé, plus les permissions sont importantes",
    )
    description = models.TextField(blank=True, verbose_name="Description des permissions")
    color = models.CharField(
        max_length=7, default="#808080", verbose_name="Couleur (hex)", help_text="Pour l'affichage dans le front"
    )

    class Meta:
        verbose_name = "Rôle de permission"
        verbose_name_plural = "Rôles de permissions"
        unique_together = ["game", "slug"]
        ordering = ["game", "-level"]

    def __str__(self):
        return f"{self.game.name} - {self.name} (lvl {self.level})"
