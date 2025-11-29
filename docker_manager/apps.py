from django.apps import AppConfig


class DockerManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "docker_manager"
    verbose_name = "Gestionnaire Docker"

    def ready(self):
        from django.conf import settings

        print(">>>> DOCKER_HOST", settings.DOCKER_HOST)
        return super().ready()
