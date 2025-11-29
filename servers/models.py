from django.conf import settings
from django.db import models

from games.models import Game, GameMod, GameVersion


class ServerInstance(models.Model):
    """Instance d'un serveur de jeu"""

    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    UPDATING = "updating"
    ERROR = "error"

    STATUS_CHOICES = [
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="stopped", verbose_name="Statut")
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
    """Configuration spécifique d'une instance de serveur"""

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


class ServerMod(models.Model):
    """Mods installés sur une instance de serveur"""

    server = models.ForeignKey(
        ServerInstance,
        on_delete=models.CASCADE,
        related_name="installed_mods",
        verbose_name="Serveur",
    )
    mod = models.ForeignKey(
        GameMod,
        on_delete=models.CASCADE,
        related_name="server_installations",
        verbose_name="Mod",
    )
    is_enabled = models.BooleanField(default=True, verbose_name="Activé")
    custom_config = models.JSONField(default=dict, blank=True, verbose_name="Configuration personnalisée")
    installed_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'installation")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière mise à jour")

    class Meta:
        verbose_name = "Mod installé"
        verbose_name_plural = "Mods installés"
        unique_together = ["server", "mod"]
        ordering = ["mod__name"]

    def __str__(self):
        return f"{self.mod.name} sur {self.server.name}"


class ServerStatus(models.Model):
    """Historique des statuts d'un serveur"""

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


class ServerPlayer(models.Model):
    """Joueurs autorisés sur un serveur (whitelist/permissions)"""

    PERMISSION_CHOICES = [
        ("player", "Joueur"),
        ("moderator", "Modérateur"),
        ("admin", "Administrateur"),
    ]

    server = models.ForeignKey(
        ServerInstance,
        on_delete=models.CASCADE,
        related_name="players",
        verbose_name="Serveur",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="server_access",
        verbose_name="Utilisateur",
        null=True,
        blank=True,
    )
    minecraft_username = models.CharField(max_length=16, blank=True, verbose_name="Pseudo Minecraft")
    minecraft_uuid = models.CharField(max_length=36, blank=True, verbose_name="UUID Minecraft")
    permission_level = models.CharField(
        max_length=20,
        choices=PERMISSION_CHOICES,
        default="player",
        verbose_name="Niveau de permission",
    )
    is_banned = models.BooleanField(default=False, verbose_name="Banni")
    ban_reason = models.TextField(blank=True, verbose_name="Raison du bannissement")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Dernière connexion")

    class Meta:
        verbose_name = "Joueur du serveur"
        verbose_name_plural = "Joueurs des serveurs"
        unique_together = ["server", "minecraft_username"]
        ordering = ["minecraft_username"]

    def __str__(self):
        return f"{self.minecraft_username or self.user.username} sur {self.server.name}"


class ServerMetrics(models.Model):
    """Métriques en temps réel d'un serveur"""

    server = models.ForeignKey(ServerInstance, on_delete=models.CASCADE, related_name="metrics", verbose_name="Serveur")
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
