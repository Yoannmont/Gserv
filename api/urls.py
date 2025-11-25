from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from accounts.views import CustomTokenObtainPairView, UserViewSet
from games.views import GameConfigurationViewSet, GameModViewSet, GameVersionViewSet, GameViewSet
from servers.views import ServerInstanceViewSet, ServerModViewSet, ServerPlayerViewSet

# Création du router principal
router = DefaultRouter()

# Routes pour accounts
router.register(r"users", UserViewSet, basename="user")

# Routes pour games
router.register(r"games", GameViewSet, basename="game")
router.register(r"game-versions", GameVersionViewSet, basename="gameversion")
router.register(r"game-mods", GameModViewSet, basename="gamemod")
router.register(r"game-configurations", GameConfigurationViewSet, basename="gameconfiguration")

# Routes pour servers
router.register(r"servers", ServerInstanceViewSet, basename="server")
router.register(r"server-mods", ServerModViewSet, basename="servermod")
router.register(r"server-players", ServerPlayerViewSet, basename="serverplayer")

urlpatterns = [
    # JWT Authentication endpoints
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # Router URLs
    path("", include(router.urls)),
]
