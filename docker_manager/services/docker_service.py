import logging
from typing import Any

import docker

logger = logging.getLogger(__name__)


class DockerServiceError(Exception):
    """Exception personnalisée pour les erreurs Docker"""

    pass


class DockerService:
    """Service de gestion des conteneurs Docker"""

    def __init__(self):
        """Initialise la connexion au daemon Docker"""
        try:
            self.client = docker.from_env()
            # Test de connexion
            self.client.ping()
            logger.info("Connexion au daemon Docker réussie")
        except docker.errors.DockerException as e:
            logger.error(f"Impossible de se connecter au daemon Docker: {e}")
            raise DockerServiceError(f"Connexion Docker échouée: {e}")

    def create_container(
        self,
        image: str,
        name: str,
        ports: dict[str, int],
        environment: dict[str, str],
        volumes: dict[str, dict[str, str]],
        memory_limit: str = "2g",
        cpu_limit: float = 2.0,
        restart_policy: dict[str, Any] | None = None,
        detach: bool = True,
    ) -> str:
        """
        Crée un conteneur Docker

        Args:
            image: Image Docker (ex: "itzg/minecraft-server:latest")
            name: Nom du conteneur
            ports: Mapping des ports {container_port: host_port}
            environment: Variables d'environnement
            volumes: Volumes à monter {host_path: {'bind': container_path, 'mode': 'rw'}}
            memory_limit: Limite mémoire (ex: "2g", "4g")
            cpu_limit: Limite CPU (nombre de cores, ex: 2.0)
            restart_policy: Politique de redémarrage
            detach: Lancer en arrière-plan

        Returns:
            container_id: ID du conteneur créé
        """
        try:
            logger.info(f"Création du conteneur {name} avec l'image {image}")

            # Pull l'image si nécessaire
            self._pull_image(image)

            # Politique de redémarrage par défaut
            if restart_policy is None:
                restart_policy = {"Name": "unless-stopped"}

            # Création du conteneur
            container = self.client.containers.create(
                image=image,
                name=name,
                ports=ports,
                environment=environment,
                volumes=volumes,
                mem_limit=memory_limit,
                nano_cpus=int(cpu_limit * 1e9),  # Conversion en nano CPUs
                restart_policy=restart_policy,
                detach=detach,
                stdin_open=True,
                tty=True,
            )

            logger.info(f"Conteneur {name} créé avec ID: {container.id}")
            return container.id

        except docker.errors.APIError as e:
            logger.error(f"Erreur API Docker lors de la création: {e}")
            raise DockerServiceError(f"Erreur lors de la création du conteneur: {e}")
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la création: {e}")
            raise DockerServiceError(f"Erreur inattendue: {e}")

    def start_container(self, container_id: str) -> bool:
        """
        Démarre un conteneur

        Args:
            container_id: ID du conteneur

        Returns:
            True si démarré avec succès
        """
        try:
            container = self.client.containers.get(container_id)
            container.start()
            logger.info(f"Conteneur {container_id} démarré")
            return True
        except docker.errors.NotFound:
            logger.error(f"Conteneur {container_id} introuvable")
            raise DockerServiceError(f"Conteneur {container_id} introuvable")
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors du démarrage: {e}")
            raise DockerServiceError(f"Erreur lors du démarrage: {e}")

    def stop_container(self, container_id: str, timeout: int = 30) -> bool:
        """
        Arrête un conteneur

        Args:
            container_id: ID du conteneur
            timeout: Timeout en secondes avant force kill

        Returns:
            True si arrêté avec succès
        """
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"Conteneur {container_id} arrêté")
            return True
        except docker.errors.NotFound:
            logger.error(f"Conteneur {container_id} introuvable")
            raise DockerServiceError(f"Conteneur {container_id} introuvable")
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors de l'arrêt: {e}")
            raise DockerServiceError(f"Erreur lors de l'arrêt: {e}")

    def restart_container(self, container_id: str, timeout: int = 30) -> bool:
        """
        Redémarre un conteneur

        Args:
            container_id: ID du conteneur
            timeout: Timeout avant force restart

        Returns:
            True si redémarré avec succès
        """
        try:
            container = self.client.containers.get(container_id)
            container.restart(timeout=timeout)
            logger.info(f"Conteneur {container_id} redémarré")
            return True
        except docker.errors.NotFound:
            logger.error(f"Conteneur {container_id} introuvable")
            raise DockerServiceError(f"Conteneur {container_id} introuvable")
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors du redémarrage: {e}")
            raise DockerServiceError(f"Erreur lors du redémarrage: {e}")

    def remove_container(self, container_id: str, force: bool = False, volumes: bool = False) -> bool:
        """
        Supprime un conteneur

        Args:
            container_id: ID du conteneur
            force: Forcer la suppression même si en cours
            volumes: Supprimer les volumes associés

        Returns:
            True si supprimé avec succès
        """
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force, v=volumes)
            logger.info(f"Conteneur {container_id} supprimé")
            return True
        except docker.errors.NotFound:
            logger.warning(f"Conteneur {container_id} déjà supprimé")
            return True
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors de la suppression: {e}")
            raise DockerServiceError(f"Erreur lors de la suppression: {e}")

    def get_container_status(self, container_id: str) -> str:
        """
        Récupère le statut d'un conteneur

        Args:
            container_id: ID du conteneur

        Returns:
            Statut du conteneur (running, exited, etc.)
        """
        try:
            container = self.client.containers.get(container_id)
            return container.status
        except docker.errors.NotFound:
            return "not_found"
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors de la récupération du statut: {e}")
            raise DockerServiceError(f"Erreur lors de la récupération du statut: {e}")

    def get_container_stats(self, container_id: str) -> dict[str, Any]:
        """
        Récupère les statistiques d'un conteneur

        Args:
            container_id: ID du conteneur

        Returns:
            Dictionnaire avec CPU, mémoire, réseau, etc.
        """
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)

            # Calcul du pourcentage CPU
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"]) * 100.0

            # Mémoire
            memory_usage = stats["memory_stats"]["usage"]
            memory_limit = stats["memory_stats"]["limit"]
            memory_percent = (memory_usage / memory_limit) * 100.0

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage": memory_usage / (1024 * 1024),  # En MB
                "memory_limit": memory_limit / (1024 * 1024),  # En MB
                "memory_percent": round(memory_percent, 2),
                "network_rx": stats["networks"]["eth0"]["rx_bytes"] if "networks" in stats else 0,
                "network_tx": stats["networks"]["eth0"]["tx_bytes"] if "networks" in stats else 0,
            }
        except docker.errors.NotFound:
            raise DockerServiceError(f"Conteneur {container_id} introuvable")
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors de la récupération des stats: {e}")
            raise DockerServiceError(f"Erreur lors de la récupération des stats: {e}")

    def get_container_logs(self, container_id: str, tail: int = 100, timestamps: bool = True) -> str:
        """
        Récupère les logs d'un conteneur

        Args:
            container_id: ID du conteneur
            tail: Nombre de dernières lignes
            timestamps: Inclure les timestamps

        Returns:
            Logs du conteneur
        """
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=timestamps)
            return logs.decode("utf-8")
        except docker.errors.NotFound:
            raise DockerServiceError(f"Conteneur {container_id} introuvable")
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors de la récupération des logs: {e}")
            raise DockerServiceError(f"Erreur lors de la récupération des logs: {e}")

    def execute_command(self, container_id: str, command: str) -> str:
        """
        Execute une commande dans un conteneur

        Args:
            container_id: ID du conteneur
            command: Commande à exécuter

        Returns:
            Sortie de la commande
        """
        try:
            container = self.client.containers.get(container_id)
            result = container.exec_run(command)
            return result.output.decode("utf-8")
        except docker.errors.NotFound:
            raise DockerServiceError(f"Conteneur {container_id} introuvable")
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors de l'exécution de la commande: {e}")
            raise DockerServiceError(f"Erreur lors de l'exécution: {e}")

    def update_container(self, container_id: str, image: str, preserve_data: bool = True) -> str:
        """
        Met à jour un conteneur vers une nouvelle version

        Args:
            container_id: ID du conteneur actuel
            image: Nouvelle image
            preserve_data: Conserver les volumes de données

        Returns:
            ID du nouveau conteneur
        """
        try:
            # Récupère la config actuelle
            old_container = self.client.containers.get(container_id)
            config = old_container.attrs

            # Arrête et supprime l'ancien conteneur
            self.stop_container(container_id)

            # Pull la nouvelle image
            self._pull_image(image)

            # Extrait la configuration
            name = config["Name"].lstrip("/")
            ports = {}
            if config["HostConfig"]["PortBindings"]:
                for container_port, host_config in config["HostConfig"]["PortBindings"].items():
                    ports[container_port] = int(host_config[0]["HostPort"])

            environment = config["Config"]["Env"]
            volumes = config["HostConfig"]["Binds"] if preserve_data else None

            # Supprime l'ancien conteneur
            self.remove_container(container_id, force=True, volumes=not preserve_data)

            # Crée le nouveau conteneur
            new_container_id = self.create_container(
                image=image,
                name=name,
                ports=ports,
                environment={var.split("=")[0]: var.split("=")[1] for var in environment if "=" in var},
                volumes=volumes or {},
                memory_limit=config["HostConfig"]["Memory"],
                cpu_limit=config["HostConfig"]["NanoCpus"] / 1e9,
            )

            logger.info(f"Conteneur mis à jour: {container_id} -> {new_container_id}")
            return new_container_id

        except docker.errors.NotFound:
            raise DockerServiceError(f"Conteneur {container_id} introuvable")
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors de la mise à jour: {e}")
            raise DockerServiceError(f"Erreur lors de la mise à jour: {e}")

    def _pull_image(self, image: str) -> None:
        """
        Pull une image Docker si elle n'existe pas localement

        Args:
            image: Nom de l'image
        """
        try:
            logger.info(f"Vérification de l'image {image}")
            self.client.images.pull(image)
            logger.info(f"Image {image} prête")
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors du pull de l'image {image}: {e}")
            raise DockerServiceError(f"Erreur lors du pull de l'image: {e}")

    def list_containers(self, all: bool = False) -> list[dict[str, Any]]:
        """
        Liste tous les conteneurs

        Args:
            all: Inclure les conteneurs arrêtés

        Returns:
            Liste des conteneurs avec leurs infos
        """
        try:
            containers = self.client.containers.list(all=all)
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                }
                for c in containers
            ]
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors du listing: {e}")
            raise DockerServiceError(f"Erreur lors du listing: {e}")

    def cleanup_unused_containers(self) -> int:
        """
        Nettoie les conteneurs inutilisés

        Returns:
            Nombre de conteneurs supprimés
        """
        try:
            removed = self.client.containers.prune()
            count = len(removed["ContainersDeleted"] or [])
            logger.info(f"{count} conteneurs inutilisés supprimés")
            return count
        except docker.errors.APIError as e:
            logger.error(f"Erreur lors du nettoyage: {e}")
            raise DockerServiceError(f"Erreur lors du nettoyage: {e}")


# Instance singleton
_docker_service = None


def get_docker_service() -> DockerService:
    """Retourne l'instance singleton du service Docker"""
    global _docker_service
    if _docker_service is None:
        _docker_service = DockerService()
    return _docker_service
