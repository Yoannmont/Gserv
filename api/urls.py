from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from accounts.views import CustomTokenObtainPairView, TokenLogoutView, UserViewSet
from games.views import GameConfigurationViewSet, GameVersionViewSet, GameViewSet
from servers.views import ServerInstanceViewSet, ServerPlayerViewSet


class NoThrottleTokenRefreshView(TokenRefreshView):
    throttle_classes = []


class NoThrottleTokenVerifyView(TokenVerifyView):
    throttle_classes = []


router = DefaultRouter()

router.register(r"users", UserViewSet, basename="user")

router.register(r"games", GameViewSet, basename="game")
router.register(r"game-versions", GameVersionViewSet, basename="gameversion")
router.register(r"game-configurations", GameConfigurationViewSet, basename="gameconfiguration")

router.register(r"servers", ServerInstanceViewSet, basename="server")
router.register(r"server-players", ServerPlayerViewSet, basename="serverplayer")

urlpatterns = [
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", NoThrottleTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", NoThrottleTokenVerifyView.as_view(), name="token_verify"),
    path("auth/logout/", TokenLogoutView.as_view(), name="token_logout"),
    path("", include(router.urls)),
]
