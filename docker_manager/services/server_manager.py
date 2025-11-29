import logging
import os

from django.conf import settings
from django.utils import timezone

from docker_manager.services.docker_service import DockerServiceError, get_docker_service
from servers.models import ServerInstance

logger = logging.getLogger(__name__)


class ServerManager:
    """Gestionnaire de haut niveau pour les serveurs de jeux"""

    def __init__(self):
        self.docker_service = get_docker_service()
        self.base_path = settings.SERVERS_DATA_PATH

    def create_server(self, server_instance) -> str:
        """
        Crée un serveur de jeu complet

        Args:
            server_instance: Instance de ServerInstance (model Django)

        Returns:
            container_id: ID du conteneur créé
        """
        try:
            logger.info(f"Création du serveur {server_instance.name}")

            # Crée les dossiers de données
            server_path = self._create_server_directories(server_instance)

            # Prépare la configuration
            ports = self._prepare_ports(server_instance)
            environment = self._prepare_environment(server_instance)
            volumes = self._prepare_volumes(server_instance, server_path)

            # Récupère les ressources
            config = server_instance.configuration
            memory_limit = config.memory_limit if hasattr(server_instance, "configuration") else "2g"
            cpu_limit = config.cpu_limit if hasattr(server_instance, "configuration") else 2.0

            # Crée le conteneur Docker
            container_id = self.docker_service.create_container(
                image=self._get_docker_image(server_instance),
                name=f"server_{server_instance.id}_{server_instance.game.slug}",
                ports=ports,
                environment=environment,
                volumes=volumes,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
            )

            logger.info(f"Serveur {server_instance.name} créé avec container_id: {container_id}")
            return container_id

        except Exception as e:
            logger.error(f"Erreur lors de la création du serveur: {e}")
            raise

    def start_server(self, server_instance) -> bool:
        """
        Démarre un serveur

        Args:
            server_instance: Instance de ServerInstance

        Returns:
            True si démarré avec succès
        """
        try:
            if not server_instance.container_id:
                raise ValueError("Le serveur n'a pas de container_id")

            logger.info(f"Démarrage du serveur {server_instance.name}")

            # Démarre le conteneur
            self.docker_service.start_container(server_instance.container_id)

            # Met à jour le timestamp
            server_instance.last_started_at = timezone.now()
            server_instance.status = ServerInstance.RUNNING
            server_instance.save(update_fields=["last_started_at", "status"])

            return True

        except DockerServiceError as e:
            logger.error(f"Erreur Docker lors du démarrage: {e}")
            server_instance.status = ServerInstance.ERROR
            server_instance.save(update_fields=["status"])
            raise

    def stop_server(self, server_instance, timeout: int = 30) -> bool:
        """
        Arrête un serveur

        Args:
            server_instance: Instance de ServerInstance
            timeout: Timeout avant force kill

        Returns:
            True si arrêté avec succès
        """
        try:
            if not server_instance.container_id:
                raise ValueError("Le serveur n'a pas de container_id")

            logger.info(f"Arrêt du serveur {server_instance.name}")

            # Arrête le conteneur
            self.docker_service.stop_container(server_instance.container_id, timeout)

            server_instance.status = ServerInstance.STOPPED
            server_instance.save(update_fields=["status"])

            return True

        except DockerServiceError as e:
            logger.error(f"Erreur Docker lors de l'arrêt: {e}")
            raise

    def restart_server(self, server_instance, timeout: int = 30) -> bool:
        """
        Redémarre un serveur

        Args:
            server_instance: Instance de ServerInstance
            timeout: Timeout

        Returns:
            True si redémarré avec succès
        """
        try:
            if not server_instance.container_id:
                raise ValueError("Le serveur n'a pas de container_id")

            logger.info(f"Redémarrage du serveur {server_instance.name}")

            self.docker_service.restart_container(server_instance.container_id, timeout)

            server_instance.last_started_at = timezone.now()
            server_instance.status = ServerInstance.RUNNING
            server_instance.save(update_fields=["last_started_at", "status"])

            return True

        except DockerServiceError as e:
            logger.error(f"Erreur Docker lors du redémarrage: {e}")
            server_instance.status = "error"
            server_instance.save(update_fields=["status"])
            raise

    def update_server(self, server_instance, new_version=None) -> str:
        """
        Met à jour un serveur vers une nouvelle version

        Args:
            server_instance: Instance de ServerInstance
            new_version: Nouvelle GameVersion (optionnel)

        Returns:
            Nouveau container_id
        """
        try:
            logger.info(f"Mise à jour du serveur {server_instance.name}")

            # Arrête le serveur
            if server_instance.is_running:
                self.stop_server(server_instance)

            # Détermine la nouvelle image
            if new_version:
                server_instance.game_version = new_version
                server_instance.save(update_fields=["game_version"])

            new_image = self._get_docker_image(server_instance)

            # Met à jour le conteneur
            new_container_id = self.docker_service.update_container(
                container_id=server_instance.container_id, image=new_image, preserve_data=True
            )

            server_instance.container_id = new_container_id
            server_instance.status = ServerInstance.STOPPED
            server_instance.save(update_fields=["container_id", "status"])

            logger.info(f"Serveur {server_instance.name} mis à jour")
            return new_container_id

        except DockerServiceError as e:
            logger.error(f"Erreur lors de la mise à jour: {e}")
            server_instance.status = "error"
            server_instance.save(update_fields=["status"])
            raise

    def delete_server(self, server_instance, delete_data: bool = False) -> bool:
        """
        Supprime un serveur

        Args:
            server_instance: Instance de ServerInstance
            delete_data: Supprimer aussi les données

        Returns:
            True si supprimé avec succès
        """
        try:
            logger.info(f"Suppression du serveur {server_instance.name}")

            if server_instance.container_id:
                # Arrête et supprime le conteneur
                try:
                    self.docker_service.stop_container(server_instance.container_id)
                except Exception:
                    pass  # Déjà arrêté

                self.docker_service.remove_container(server_instance.container_id, force=True, volumes=delete_data)

            # Supprime les fichiers si demandé
            if delete_data:
                server_path = self._get_server_path(server_instance)
                if os.path.exists(server_path):
                    import shutil

                    shutil.rmtree(server_path)
                    logger.info(f"Données du serveur supprimées: {server_path}")

            return True

        except DockerServiceError as e:
            logger.error(f"Erreur lors de la suppression: {e}")
            raise

    def get_server_stats(self, server_instance) -> dict:
        """
        Récupère les statistiques d'un serveur

        Args:
            server_instance: Instance de ServerInstance

        Returns:
            Dictionnaire de statistiques
        """
        try:
            if not server_instance.container_id:
                return {}

            stats = self.docker_service.get_container_stats(server_instance.container_id)

            # Ajoute les infos spécifiques au jeu
            stats["players_online"] = self._get_players_count(server_instance)
            stats["uptime"] = self._get_uptime(server_instance)

            return stats

        except DockerServiceError:
            return {}

    def get_server_logs(self, server_instance, tail: int = 100) -> str:
        """
        Récupère les logs d'un serveur

        Args:
            server_instance: Instance de ServerInstance
            tail: Nombre de lignes

        Returns:
            Logs du serveur
        """
        try:
            if not server_instance.container_id:
                return "Aucun conteneur associé"

            return self.docker_service.get_container_logs(server_instance.container_id, tail=tail)

        except DockerServiceError as e:
            return f"Erreur lors de la récupération des logs: {e}"

    def execute_command(self, server_instance, command: str) -> str:
        """
        Execute une commande dans le serveur

        Args:
            server_instance: Instance de ServerInstance
            command: Commande à exécuter

        Returns:
            Sortie de la commande
        """
        try:
            if not server_instance.container_id:
                raise ValueError("Le serveur n'a pas de container_id")

            return self.docker_service.execute_command(server_instance.container_id, command)

        except DockerServiceError as e:
            logger.error(f"Erreur lors de l'exécution de la commande: {e}")
            raise

    def install_mod(self, server_instance, mod) -> bool:
        """
        Installe un mod sur un serveur

        Args:
            server_instance: Instance de ServerInstance
            mod: Instance de GameMod

        Returns:
            True si installé avec succès
        """
        try:
            logger.info(f"Installation du mod {mod.name} sur {server_instance.name}")

            # Chemin du dossier mods
            mods_path = os.path.join(self._get_server_path(server_instance), "mods")
            os.makedirs(mods_path, exist_ok=True)

            # Télécharge le mod
            import requests

            response = requests.get(mod.download_url, stream=True)
            response.raise_for_status()

            mod_file_path = os.path.join(mods_path, mod.file_name)
            with open(mod_file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Mod {mod.name} installé: {mod_file_path}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'installation du mod: {e}")
            raise

    def uninstall_mod(self, server_instance, mod) -> bool:
        """
        Désinstalle un mod d'un serveur

        Args:
            server_instance: Instance de ServerInstance
            mod: Instance de GameMod

        Returns:
            True si désinstallé avec succès
        """
        try:
            logger.info(f"Désinstallation du mod {mod.name} de {server_instance.name}")

            mod_file_path = os.path.join(self._get_server_path(server_instance), "mods", mod.file_name)

            if os.path.exists(mod_file_path):
                os.remove(mod_file_path)
                logger.info(f"Mod {mod.name} désinstallé")

            return True

        except Exception as e:
            logger.error(f"Erreur lors de la désinstallation du mod: {e}")
            raise

    # Méthodes privées

    def _create_server_directories(self, server_instance) -> str:
        """Crée les dossiers nécessaires pour un serveur"""
        server_path = self._get_server_path(server_instance)

        directories = [
            server_path,
            os.path.join(server_path, "data"),
            os.path.join(server_path, "mods"),
            os.path.join(server_path, "config"),
            os.path.join(server_path, "backups"),
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)

        logger.info(f"Dossiers créés pour {server_instance.name}: {server_path}")
        return server_path

    def _get_server_path(self, server_instance) -> str:
        """Retourne le chemin du serveur"""
        return os.path.join(self.base_path, server_instance.game.slug, f"server_{server_instance.id}")

    def _get_docker_image(self, server_instance) -> str:
        """Construit le nom complet de l'image Docker"""
        game = server_instance.game
        version = server_instance.game_version

        # Si la version a un tag Docker spécifique
        if version.docker_tag:
            return f"{game.docker_image}:{version.docker_tag}"

        # Sinon utilise la version directement
        return f"{game.docker_image}:{version.version}"

    def _prepare_ports(self, server_instance) -> dict:
        """Prépare le mapping des ports"""
        return server_instance.get_all_port_mappings()

    def _prepare_environment(self, server_instance) -> dict:
        """Prépare les variables d'environnement"""
        env = {}

        if hasattr(server_instance, "configuration"):
            config = server_instance.configuration
            env.update(config.environment_variables)

        # Ajoute des variables communes
        env["SERVER_NAME"] = server_instance.name
        env["MAX_PLAYERS"] = str(server_instance.max_players)

        return env

    def _prepare_volumes(self, server_instance, server_path: str) -> dict:
        """Prépare les volumes Docker"""
        return {
            os.path.join(server_path, "data"): {"bind": "/data", "mode": "rw"},
            os.path.join(server_path, "mods"): {"bind": "/mods", "mode": "rw"},
            os.path.join(server_path, "config"): {"bind": "/config", "mode": "rw"},
        }

    def _get_players_count(self, server_instance) -> int:
        """Récupère le nombre de joueurs connectés"""
        # TODO: Implémenter selon le jeu
        # Pour Minecraft: query RCON ou parse logs
        # Pour Palworld: API spécifique
        return 0

    def _get_uptime(self, server_instance) -> int:
        """Récupère l'uptime en secondes"""
        if not server_instance.last_started_at:
            return 0

        delta = timezone.now() - server_instance.last_started_at
        return int(delta.total_seconds())


# Instance singleton
_server_manager = None


def get_server_manager() -> ServerManager:
    """Retourne l'instance singleton du gestionnaire de serveurs"""
    global _server_manager
    if _server_manager is None:
        _server_manager = ServerManager()
    return _server_manager
