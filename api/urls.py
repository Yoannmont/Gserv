from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import (
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    TokenLogoutView,
    UserViewSet,
)
from games.views import GameViewSet
from servers.views import (
    ServerInstanceViewSet,
)

router = DefaultRouter()

router.register(r"users", UserViewSet, basename="user")

router.register(r"games", GameViewSet, basename="game")

router.register(r"servers", ServerInstanceViewSet, basename="server")


urlpatterns = [
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", TokenLogoutView.as_view(), name="token_logout"),
    path("", include(router.urls)),
]
