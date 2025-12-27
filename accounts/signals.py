import logging

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from accounts.models import User

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=User)
def delete_user_avatar(sender, instance, **kwargs):
    """
    Supprime le fichier avatar lorsqu'un utilisateur est supprimé.
    """
    if instance.avatar:
        try:
            storage = instance.avatar.storage
            if storage.exists(instance.avatar.name):
                storage.delete(instance.avatar.name)
                logger.info(
                    f"[accounts_signals] Avatar supprimé pour l'utilisateur {instance.id}: {instance.avatar.name}"
                )
        except Exception as e:
            logger.error(
                f"[accounts_signals] Erreur lors de la suppression de l'avatar pour l'utilisateur {instance.id}: {str(e)}"
            )
