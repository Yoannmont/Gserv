import re

from django.conf import settings
from django.db import models
from django.db.models import Q

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

    ACTIVE_STATUS = [CREATING, CREATED, STARTING, RUNNING, UPDATING]

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
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=CREATING,
        verbose_name="Statut",
        db_index=True,
    )
    container_id = models.CharField(max_length=64, blank=True, null=True, verbose_name="ID du conteneur Docker")
    port = models.IntegerField(verbose_name="Port", help_text="Port externe du serveur", db_index=True)
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
    is_public = models.BooleanField(default=False, verbose_name="Serveur public", db_index=True)
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

    def get_all_host_ports(self):
        """Return all host ports used by this server (main port + additional ports)"""
        ports = [self.port]

        if self.additional_ports:
            for host_port in self.additional_ports.values():
                if isinstance(host_port, int):
                    ports.append(host_port)

        return ports

    @classmethod
    def is_port_available(cls, port, additional_ports=None, exclude_server_id=None):
        """
        Check if a port (or ports) is available for use.

        Args:
            port: Main port to check
            additional_ports: Dict of additional ports to check (optional)
            exclude_server_id: Server ID to exclude from the check (for updates)

        Returns:
            tuple: (is_available: bool, conflicting_server: ServerInstance or None, conflicting_port: int or None)
        """
        active_servers = queryset = cls.objects.filter(Q(status__in=cls.ACTIVE_STATUS) | Q(container_id__isnull=False))

        queryset = active_servers.filter(port=port)

        if exclude_server_id:
            queryset = queryset.exclude(id=exclude_server_id)

        conflicting_server = queryset.first()
        if conflicting_server:
            return False, conflicting_server, port

        for server in active_servers:
            if server.additional_ports:
                for server_host_port in server.additional_ports.values():
                    if isinstance(server_host_port, int) and server_host_port == port:
                        return False, server, server_host_port

        if additional_ports:
            for host_port in additional_ports.values():
                if isinstance(host_port, int):
                    queryset = active_servers.filter(port=host_port)
                    if exclude_server_id:
                        queryset = queryset.exclude(id=exclude_server_id)

                    conflicting_server = queryset.first()
                    if conflicting_server:
                        return False, conflicting_server, host_port

                    queryset = active_servers
                    if exclude_server_id:
                        queryset = queryset.exclude(id=exclude_server_id)

                    for server in queryset:
                        if server.additional_ports:
                            for server_host_port in server.additional_ports.values():
                                if isinstance(server_host_port, int) and server_host_port == host_port:
                                    return False, server, server_host_port

        return True, None, None

    @staticmethod
    def parse_memory(memory_str):
        """
        Parse memory string (e.g., "2g", "512m", "4g") to bytes.

        Args:
            memory_str: Memory string (e.g., "2g", "512m")

        Returns:
            int: Memory in bytes
        """
        if not memory_str:
            return 0

        memory_str = memory_str.lower().strip()
        match = re.match(r"^(\d+(?:\.\d+)?)\s*([kmgt]?)$", memory_str)

        if not match:
            raise ValueError(f"Invalid memory format: {memory_str}")

        value = float(match.group(1))
        unit = match.group(2) or ""

        multipliers = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}
        return int(value * multipliers.get(unit, 1))

    @classmethod
    def get_global_resources(cls, exclude_server_id=None):
        """
        Calculate total resources (memory and CPU) used by all active servers.

        Args:
            exclude_server_id: Server ID to exclude from calculation (optional)

        Returns:
            tuple: (total_memory_bytes: int, total_cpu: float)
        """
        queryset = cls.objects.filter(status__in=cls.ACTIVE_STATUS)

        if exclude_server_id:
            queryset = queryset.exclude(id=exclude_server_id)

        total_memory_bytes = 0
        total_cpu = 0.0

        for server in queryset.select_related("configuration"):
            if hasattr(server, "configuration"):
                config = server.configuration
                try:
                    total_memory_bytes += cls.parse_memory(config.memory_limit)
                except (ValueError, AttributeError):
                    pass
                total_cpu += config.cpu_limit

        return total_memory_bytes, total_cpu

    @classmethod
    def check_resources_available(cls, memory_limit, cpu_limit, exclude_server_id=None, force=False):
        """
        Check if adding a server with given resources would exceed global limits.

        Args:
            memory_limit: Memory limit string (e.g., "2g")
            cpu_limit: CPU limit (float)
            exclude_server_id: Server ID to exclude from calculation (optional)
            force: If True, skip resource check

        Returns:
            tuple: (is_available: bool, error_message: str or None)
        """
        if force:
            return True, None

        try:
            new_memory_bytes = cls.parse_memory(memory_limit)
        except ValueError as e:
            return False, f"Format de mémoire invalide: {str(e)}"

        max_memory_global = getattr(settings, "MAX_MEMORY_GLOBAL", None)
        max_cpu_global = getattr(settings, "MAX_CPU_GLOBAL", None)

        if not max_memory_global and not max_cpu_global:
            return True, None

        global_memory, global_cpu = cls.get_global_resources(exclude_server_id=exclude_server_id)
        total_global_memory = global_memory + new_memory_bytes
        total_global_cpu = global_cpu + cpu_limit

        if max_memory_global:
            try:
                max_memory_bytes = cls.parse_memory(max_memory_global)
                if total_global_memory > max_memory_bytes:
                    return False, (
                        f"Limite de mémoire globale dépassée: "
                        f"{total_global_memory / (1024**3):.2f}GB utilisés sur {max_memory_bytes / (1024**3):.2f}GB maximum"
                    )
            except ValueError:
                pass

        if max_cpu_global:
            if total_global_cpu > max_cpu_global:
                return False, (
                    f"Limite de CPU globale dépassée: {total_global_cpu:.2f} CPU utilisés sur {max_cpu_global:.2f} maximum"
                )

        return True, None


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
    status = models.CharField(
        max_length=20,
        choices=ServerInstance.STATUS_CHOICES,
        verbose_name="Statut",
        db_index=True,
    )
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
        db_index=True,
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
