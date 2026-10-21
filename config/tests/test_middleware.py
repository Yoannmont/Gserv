import pytest
from django.http import HttpRequest, HttpResponseForbidden
from django.test import override_settings

from accounts.models import AllowedAdminIP
from config.middleware import AdminIPRestrictionMiddleware


@pytest.mark.django_db
class TestAdminIPRestrictionMiddleware:
    def setup_method(self):
        self.middleware = AdminIPRestrictionMiddleware(lambda r: None)

    def test_non_admin_path_allowed(self):
        request = HttpRequest()
        request.path = "/api/servers/"
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        response = self.middleware.process_request(request)

        assert response is None

    def test_admin_path_without_allowed_ip_blocked(self):
        request = HttpRequest()
        request.path = "/gserv-console/"
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        response = self.middleware.process_request(request)

        assert isinstance(response, HttpResponseForbidden)
        assert "192.168.1.100" in str(response.content)

    def test_admin_path_with_allowed_ip_allowed(self):
        AllowedAdminIP.objects.create(ip_address="192.168.1.100", is_active=True)

        request = HttpRequest()
        request.path = "/gserv-console/"
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        response = self.middleware.process_request(request)

        assert response is None
        AllowedAdminIP.objects.all().delete()

    def test_admin_path_with_inactive_ip_blocked(self):
        AllowedAdminIP.objects.create(ip_address="192.168.1.100", is_active=False)

        request = HttpRequest()
        request.path = "/gserv-console/"
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        response = self.middleware.process_request(request)

        assert isinstance(response, HttpResponseForbidden)
        AllowedAdminIP.objects.all().delete()

    @override_settings(DEBUG=True, ADMIN_IP_RESTRICTION_DISABLED_IN_DEBUG=True)
    def test_debug_mode_bypasses_restriction(self):
        request = HttpRequest()
        request.path = "/gserv-console/"
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        response = self.middleware.process_request(request)

        assert response is None

    def test_get_client_ip_with_x_forwarded_for(self):
        request = HttpRequest()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.195, 70.41.3.18, 150.172.238.178",
            "REMOTE_ADDR": "192.168.1.1",
        }

        ip = self.middleware.get_client_ip(request)

        assert ip == "203.0.113.195"

    def test_get_client_ip_without_x_forwarded_for(self):
        request = HttpRequest()
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        ip = self.middleware.get_client_ip(request)

        assert ip == "192.168.1.100"

    def test_admin_path_with_multiple_allowed_ips(self):
        AllowedAdminIP.objects.create(ip_address="192.168.1.100", is_active=True)
        AllowedAdminIP.objects.create(ip_address="10.0.0.1", is_active=True)

        request = HttpRequest()
        request.path = "/gserv-console/"
        request.META = {"REMOTE_ADDR": "10.0.0.1"}

        response = self.middleware.process_request(request)

        assert response is None
        AllowedAdminIP.objects.all().delete()

    def test_cache_invalidation_after_ip_added(self):
        request = HttpRequest()
        request.path = "/gserv-console/"
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        response = self.middleware.process_request(request)
        assert isinstance(response, HttpResponseForbidden)

        AllowedAdminIP.objects.create(ip_address="192.168.1.100", is_active=True)

        middleware2 = AdminIPRestrictionMiddleware(lambda r: None)
        response = middleware2.process_request(request)

        assert response is None
        AllowedAdminIP.objects.all().delete()

    def test_admin_subpath_blocked(self):
        request = HttpRequest()
        request.path = "/gserv-console/accounts/user/"
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        response = self.middleware.process_request(request)

        assert isinstance(response, HttpResponseForbidden)

    def test_ipv6_address_allowed(self):
        AllowedAdminIP.objects.create(ip_address="2001:db8::1", is_active=True)

        request = HttpRequest()
        request.path = "/gserv-console/"
        request.META = {"REMOTE_ADDR": "2001:db8::1"}

        response = self.middleware.process_request(request)

        assert response is None
        AllowedAdminIP.objects.all().delete()
