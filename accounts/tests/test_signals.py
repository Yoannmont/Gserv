import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import AllowedAdminIP, User


@pytest.mark.django_db
class TestUserSignals:
    def test_delete_user_with_avatar(self):
        avatar_content = b"fake_image_content"
        avatar = SimpleUploadedFile("test_avatar.jpg", avatar_content, content_type="image/jpeg")

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            avatar=avatar,
        )

        user_id = user.id

        user.delete()

        assert not User.objects.filter(id=user_id).exists()

    def test_delete_user_without_avatar(self):
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        user_id = user.id
        user.delete()

        assert not User.objects.filter(id=user_id).exists()


@pytest.mark.django_db
class TestAllowedAdminIPSignals:
    def test_cache_invalidated_on_create(self):
        cache.set("allowed_admin_ips", {"192.168.1.1"})

        AllowedAdminIP.objects.create(ip_address="192.168.1.100", is_active=True)

        cached_ips = cache.get("allowed_admin_ips")
        assert cached_ips is None

    def test_cache_invalidated_on_update(self):
        ip = AllowedAdminIP.objects.create(ip_address="192.168.1.100", is_active=True)
        cache.set("allowed_admin_ips", {"192.168.1.100"})

        ip.is_active = False
        ip.save()

        cached_ips = cache.get("allowed_admin_ips")
        assert cached_ips is None

    def test_cache_invalidated_on_delete(self):
        ip = AllowedAdminIP.objects.create(ip_address="192.168.1.100", is_active=True)
        cache.set("allowed_admin_ips", {"192.168.1.100"})

        ip.delete()

        cached_ips = cache.get("allowed_admin_ips")
        assert cached_ips is None

    def test_multiple_operations_invalidate_cache(self):
        cache.set("allowed_admin_ips", {"192.168.1.1"})

        ip1 = AllowedAdminIP.objects.create(ip_address="192.168.1.100", is_active=True)
        assert cache.get("allowed_admin_ips") is None

        cache.set("allowed_admin_ips", {"192.168.1.100"})

        AllowedAdminIP.objects.create(ip_address="192.168.1.101", is_active=True)
        assert cache.get("allowed_admin_ips") is None

        cache.set("allowed_admin_ips", {"192.168.1.100", "192.168.1.101"})

        ip1.delete()
        assert cache.get("allowed_admin_ips") is None
