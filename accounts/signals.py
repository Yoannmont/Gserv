import logging

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from accounts.models import AllowedAdminIP, User

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=User)
def delete_user_avatar(sender, instance, **kwargs):
    """
    Delete the user avatar when a user is deleted.
    """
    if instance.avatar:
        try:
            storage = instance.avatar.storage
            if storage.exists(instance.avatar.name):
                storage.delete(instance.avatar.name)
                logger.info(f"[accounts_signals] Avatar deleted for user {instance.id}: {instance.avatar.name}")
        except Exception as e:
            logger.error(f"[accounts_signals] Error deleting avatar for user {instance.id}: {str(e)}")


@receiver([post_save, post_delete], sender=AllowedAdminIP)
def invalidate_admin_ip_cache(sender, instance, **kwargs):
    """
    Invalidate the allowed admin IPs cache when an IP is added, modified or deleted.
    """
    cache_key = "allowed_admin_ips"
    cache.delete(cache_key)
    logger.info(f"[accounts_signals] Cache admin IPs invalidated after modification of IP {instance.ip_address}")
