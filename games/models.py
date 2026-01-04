from django.core.validators import URLValidator
from django.db import models


class Game(models.Model):
    """Represents a game type (Minecraft, Palworld, etc.)"""

    name = models.CharField(max_length=100, unique=True, verbose_name="Nom du jeu")
    slug = models.SlugField(unique=True, verbose_name="Slug", db_index=True)
    description = models.TextField(verbose_name="Description")
    icon = models.ImageField(upload_to="games/icons/", null=True, blank=True, verbose_name="Icône")
    docker_image = models.CharField(
        max_length=255,
        verbose_name="Image Docker",
        help_text="Ex: itzg/minecraft-server",
    )
    health_check_command = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Commande health check",
        help_text=("Commande à exécuter pour vérifier l'état du serveur. Si vide, utilise le statut du container Docker."),
    )
    default_port = models.IntegerField(verbose_name="Port par défaut")
    additional_ports = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Ports additionnels",
        help_text='Liste de ports supplémentaires: [{"port": 27015, "protocol": "udp", "description": "Query port"}]',
    )
    documentation_url = models.URLField(blank=True, validators=[URLValidator()], verbose_name="URL de documentation")
    is_active = models.BooleanField(default=True, verbose_name="Actif", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Jeu"
        verbose_name_plural = "Jeux"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_all_ports(self):
        """Return all ports (default + additional)"""
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
    created_at = models.DateTimeField(auto_now_add=True)
    docker_tag = models.CharField(max_length=40, verbose_name="Tag docker", help_text="Ex: java16", db_index=True)

    class Meta:
        verbose_name = "Version de jeu"
        verbose_name_plural = "Versions de jeux"
        unique_together = ["game", "version"]
        ordering = ["-release_date"]

    def __str__(self):
        return f"{self.game.name} - {self.version}"


class GameConfiguration(models.Model):
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="configurations",
        verbose_name="Jeu",
    )
    name = models.CharField(max_length=100, verbose_name="Nom de la configuration", db_index=True)
    description = models.TextField(blank=True, verbose_name="Description")
    is_default = models.BooleanField(default=False, verbose_name="Configuration par défaut", db_index=True)
    config_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Données de configuration par défaut",
        help_text=(
            "Configuration par défaut pour les nouveaux serveurs. "
            'Peut contenir: {"memory_limit": "2g", "cpu_limit": 2.0, '
            '"environment_variables": {}, "docker_volumes": {}, "custom_startup_command": ""}'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration de jeu"
        verbose_name_plural = "Configurations de jeux"
        ordering = ["game", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["game", "is_default"],
                condition=models.Q(is_default=True),
                name="unique_default_per_game",
            )
        ]

    def __str__(self):
        return f"{self.game.name} - {self.name}"
