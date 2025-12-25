import factory
from factory.django import DjangoModelFactory

from accounts.tests.accounts_factories import UserFactory
from games.tests.games_factories import GameFactory, GameVersionFactory
from servers.models import (
    ServerConfiguration,
    ServerInstance,
    ServerPlayer,
    ServerStatus,
)


class ServerInstanceFactory(DjangoModelFactory):
    class Meta:
        model = ServerInstance

    name = factory.Sequence(lambda n: f"Server {n}")
    game = factory.SubFactory(GameFactory)
    game_version = factory.SubFactory(GameVersionFactory)
    owner = factory.SubFactory(UserFactory)
    description = factory.Faker("text", max_nb_chars=200)
    status = "stopped"
    port = factory.Sequence(lambda n: 25565 + n)
    max_players = 20
    auto_start = False
    auto_update = False
    backup_enabled = True
    is_public = False


class ServerConfigurationFactory(DjangoModelFactory):
    class Meta:
        model = ServerConfiguration

    server = factory.SubFactory(ServerInstanceFactory)
    config_data = factory.LazyFunction(lambda: {"difficulty": "normal"})
    environment_variables = factory.LazyFunction(lambda: {"EULA": "TRUE"})
    docker_volumes = factory.LazyFunction(lambda: {"data": {"bind": "/data", "mode": "rw"}})
    memory_limit = "2g"
    cpu_limit = 2.0


class ServerStatusFactory(DjangoModelFactory):
    class Meta:
        model = ServerStatus

    server = factory.SubFactory(ServerInstanceFactory)
    status = "stopped"
    message = factory.Faker("sentence")
    triggered_by = factory.SubFactory(UserFactory)


class ServerPlayerFactory(DjangoModelFactory):
    class Meta:
        model = ServerPlayer

    server = factory.SubFactory(ServerInstanceFactory)
    user = factory.SubFactory(UserFactory)
    minecraft_username = factory.Sequence(lambda n: f"player{n}")
    minecraft_uuid = factory.Faker("uuid4")
    permission_level = "player"
    is_banned = False
