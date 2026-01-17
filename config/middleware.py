from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError, ProgrammingError
from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin


class AdminIPRestrictionMiddleware(MiddlewareMixin):
    """
    Middleware pour restreindre l'accès à l'admin Django aux IP autorisées.
    Vérifie l'IP de la requête contre la liste des IP autorisées en base de données.
    """

    CACHE_KEY = "allowed_admin_ips"
    CACHE_TIMEOUT = 300

    def process_request(self, request):
        if not request.path.startswith("/gserv-console/"):
            return None

        if getattr(settings, "ADMIN_IP_RESTRICTION_DISABLED_IN_DEBUG", False) and settings.DEBUG:
            return None

        ip_address = self.get_client_ip(request)

        if not self.is_ip_allowed(ip_address):
            return HttpResponseForbidden(
                "<h1>Accès refusé</h1>"
                "<p>Votre adresse IP n'est pas autorisée à accéder à l'interface d'administration.</p>"
                f"<p>Votre IP détectée : <strong>{ip_address}</strong></p>"
            )

        return None

    def get_client_ip(self, request):
        """
        Get the real client IP address considering proxies.
        """
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def is_ip_allowed(self, ip_address):
        """
        Vérifie si l'adresse IP est dans la liste des IP autorisées.
        Utilise le cache Django pour éviter de faire une requête DB à chaque requête.
        """
        allowed_ips = cache.get(self.CACHE_KEY)

        if allowed_ips is None:
            try:
                from accounts.models import AllowedAdminIP

                allowed_ips = set(AllowedAdminIP.objects.filter(is_active=True).values_list("ip_address", flat=True))
                cache.set(self.CACHE_KEY, allowed_ips, self.CACHE_TIMEOUT)
            except (OperationalError, ProgrammingError):
                return True

        return ip_address in allowed_ips


class OriginRestrictionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin")

        if not request.path.startswith("/gserv-console/") and (not origin or origin not in settings.CORS_ALLOWED_ORIGINS):
            return HttpResponseForbidden("Origin not allowed")

        return self.get_response(request)
