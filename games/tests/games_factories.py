import factory
from django.utils.text import slugify
from factory.django import DjangoModelFactory

from games.models import Game, GameConfiguration, GameVersion


class GameFactory(DjangoModelFactory):
    class Meta:
        model = Game

    name = factory.Sequence(lambda n: f"Game {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))
    description = factory.Faker("text", max_nb_chars=200)
    docker_image = factory.Sequence(lambda n: f"game/image:{n}")
    default_port = factory.Sequence(lambda n: 25565 + n)
    documentation_url = factory.Faker("url")
    is_active = True


class GameVersionFactory(DjangoModelFactory):
    class Meta:
        model = GameVersion

    game = factory.SubFactory(GameFactory)
    version = factory.Sequence(lambda n: f"1.{n}.0")
    release_date = factory.Faker("date_this_year")
    is_stable = True
    is_recommended = False
    changelog = factory.Faker("text")


class GameConfigurationFactory(DjangoModelFactory):
    class Meta:
        model = GameConfiguration

    game = factory.SubFactory(GameFactory)
    name = factory.Sequence(lambda n: f"Config {n}")
    description = factory.Faker("text", max_nb_chars=100)
    config_data = factory.LazyFunction(lambda: {"key": "value"})
    is_default = False
