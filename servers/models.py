from django.conf import settings
from django.db import models

from games.models import Game, GameVersion


class ServerInstance(models.Model):
    """Instance of a game server"""

    CREATING = "creating"
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    UPDATING = "updating"
    ERROR = "error"

    STATUS_CHOICES = [
        (CREATING, "Création en cours"),
        (CREATED, "Créé"),
        (STARTING, "Démarrage demandé"),
        (RUNNING, "Démarré"),
        (STOPPING, "Arrêt en cours"),
        (STOPPED, "Arrêté"),
        (UPDATING, "Mise à jour"),
        (ERROR, "Erreur"),
    ]

    name = models.CharField(max_length=100, verbose_name="Nom du serveur")
    game = models.ForeignKey(Game, on_delete=models.PROTECT, related_name="servers", verbose_name="Jeu")
    game_version = models.ForeignKey(
        GameVersion,
        on_delete=models.PROTECT,
        related_name="servers",
        verbose_name="Version du jeu",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_servers",
        verbose_name="Propriétaire",
    )
    description = models.TextField(blank=True, verbose_name="Description")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=CREATING, verbose_name="Statut")
    container_id = models.CharField(max_length=64, blank=True, null=True, verbose_name="ID du conteneur Docker")
    port = models.IntegerField(verbose_name="Port", help_text="Port externe du serveur")
    additional_ports = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Ports additionnels mappés",
        help_text='Mapping des ports additionnels: {"27015": 27016, "8212": 8213}',
    )
    max_players = models.IntegerField(default=20, verbose_name="Nombre maximum de joueurs")
    auto_start = models.BooleanField(default=False, verbose_name="Démarrage automatique")
    auto_update = models.BooleanField(default=False, verbose_name="Mise à jour automatique")
    backup_enabled = models.BooleanField(default=True, verbose_name="Sauvegardes activées")
    is_public = models.BooleanField(default=False, verbose_name="Serveur public")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")
    last_started_at = models.DateTimeField(null=True, blank=True, verbose_name="Dernier démarrage")

    class Meta:
        verbose_name = "Instance de serveur"
        verbose_name_plural = "Instances de serveurs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.game.name})"

    @property
    def is_running(self):
        return self.status == self.RUNNING

    def get_all_port_mappings(self):
        """Return all port mappings for this server"""
        mappings = {}

        # Main port (TCP + UDP)
        mappings[f"{self.game.default_port}/tcp"] = self.port
        mappings[f"{self.game.default_port}/udp"] = self.port

        # Additional ports
        for game_port_info in self.game.additional_ports:
            game_port = game_port_info["port"]
            protocol = game_port_info.get("protocol", "tcp")

            # Get custom mapping or use the same port
            host_port = self.additional_ports.get(str(game_port), game_port)

            if protocol == "both":
                mappings[f"{game_port}/tcp"] = host_port
                mappings[f"{game_port}/udp"] = host_port
            else:
                mappings[f"{game_port}/{protocol}"] = host_port

        return mappings


class ServerConfiguration(models.Model):
    """Configuration specific to a server instance"""

    server = models.OneToOneField(
        ServerInstance,
        on_delete=models.CASCADE,
        related_name="configuration",
        verbose_name="Serveur",
    )
    config_data = models.JSONField(
        default=dict,
        verbose_name="Configuration",
        help_text="Configuration complète au format JSON",
        blank=True,
    )
    environment_variables = models.JSONField(
        default=dict,
        verbose_name="Variables d'environnement",
        help_text="Variables d'environnement Docker",
        blank=True,
    )
    docker_volumes = models.JSONField(
        default=dict,
        verbose_name="Volumes Docker",
        help_text="Liste des volumes à monter (ex: {'data':  {'bind': '/palworld', 'mode': 'rw'})",
        blank=True,
    )
    memory_limit = models.CharField(
        max_length=20,
        default="2g",
        verbose_name="Limite de mémoire",
        help_text="Ex: 2g, 4g, 8g",
    )
    cpu_limit = models.FloatField(default=2.0, verbose_name="Limite CPU", help_text="Nombre de CPUs (ex: 2.0)")
    custom_startup_command = models.TextField(blank=True, verbose_name="Commande de démarrage personnalisée")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration de serveur"
        verbose_name_plural = "Configurations de serveurs"

    def __str__(self):
        return f"Configuration de {self.server.name}"


class ServerStatus(models.Model):
    """History of the status of a server"""

    server = models.ForeignKey(
        ServerInstance,
        on_delete=models.CASCADE,
        related_name="status_history",
        verbose_name="Serveur",
    )
    status = models.CharField(max_length=20, choices=ServerInstance.STATUS_CHOICES, verbose_name="Statut")
    message = models.TextField(blank=True, verbose_name="Message")
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_statuses",
        verbose_name="Déclenché par",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")

    class Meta:
        verbose_name = "Statut de serveur"
        verbose_name_plural = "Statuts de serveurs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.server.name} - {self.status} ({self.created_at})"


class ServerRole(models.Model):
    """Server roles with different permission levels"""

    ROLE_VIEWER = "viewer"
    ROLE_EDITOR = "editor"
    ROLE_MANAGER = "manager"
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = [
        (ROLE_VIEWER, "Visualiseur"),
        (ROLE_MANAGER, "Gestionnaire"),
        (ROLE_EDITOR, "Éditeur"),
        (ROLE_ADMIN, "Administrateur"),
    ]

    server = models.ForeignKey(
        ServerInstance,
        on_delete=models.CASCADE,
        related_name="roles",
        verbose_name="Serveur",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="managed_servers",
        verbose_name="Utilisateur",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_VIEWER,
        verbose_name="Rôle",
        help_text="Niveau de permission pour gérer ce serveur",
    )
    can_view = models.BooleanField(default=True, verbose_name="Peut visualiser")
    can_edit = models.BooleanField(default=False, verbose_name="Peut modifier les paramètres")
    can_control = models.BooleanField(default=False, verbose_name="Peut démarrer/arrêter/redémarrer")
    can_delete = models.BooleanField(default=False, verbose_name="Peut supprimer")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_managers",
        verbose_name="Ajouté par",
    )

    class Meta:
        verbose_name = "Rôle de serveur"
        verbose_name_plural = "Rôles de serveurs"
        unique_together = ["server", "user"]
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()} sur {self.server.name}"

    def save(self, *args, **kwargs):
        """Update automatically the permissions according to the role"""
        if self.role == self.ROLE_VIEWER:
            self.can_view = True
            self.can_edit = False
            self.can_control = False
            self.can_delete = False
        elif self.role == self.ROLE_MANAGER:
            self.can_view = True
            self.can_edit = False
            self.can_control = True
            self.can_delete = False
        elif self.role == self.ROLE_EDITOR:
            self.can_view = True
            self.can_edit = True
            self.can_control = True
            self.can_delete = False
        elif self.role == self.ROLE_ADMIN:
            self.can_view = True
            self.can_edit = True
            self.can_control = True
            self.can_delete = True

        super().save(*args, **kwargs)

    def has_permission(self, permission_type: str) -> bool:
        """Check if the manager has a specific permission"""
        if permission_type == "view":
            return self.can_view
        elif permission_type == "edit":
            return self.can_edit
        elif permission_type == "control":
            return self.can_control
        elif permission_type == "delete":
            return self.can_delete
        return False


class ServerMetrics(models.Model):
    """Real-time metrics of a server"""

    server = models.ForeignKey(
        ServerInstance,
        on_delete=models.CASCADE,
        related_name="metrics",
        verbose_name="Serveur",
    )
    cpu_usage = models.FloatField(verbose_name="Utilisation CPU (%)")
    memory_usage = models.FloatField(verbose_name="Utilisation mémoire (MB)")
    memory_percent = models.FloatField(default=0, verbose_name="Utilisation mémoire (%)")
    players_online = models.IntegerField(default=0, verbose_name="Joueurs connectés")
    tps = models.FloatField(
        null=True,
        blank=True,
        verbose_name="TPS (Ticks Per Second)",
        help_text="Pour les jeux qui supportent cette métrique",
    )
    uptime_seconds = models.IntegerField(default=0, verbose_name="Uptime (secondes)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de capture")

    class Meta:
        verbose_name = "Métrique de serveur"
        verbose_name_plural = "Métriques de serveurs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.server.name} - {self.created_at}"
