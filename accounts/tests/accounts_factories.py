import factory
from factory.django import DjangoModelFactory

from accounts.models import User, UserProfile


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    role = "user"
    is_active = True

    @factory.post_generation
    def password(obj, create, extracted):
        if create:
            password = extracted if extracted else "testpass123"
            obj.set_password(password)
            obj.save()


class AdminUserFactory(UserFactory):
    username = factory.Sequence(lambda n: f"admin{n}")
    role = "admin"


class UserProfileFactory(DjangoModelFactory):
    class Meta:
        model = UserProfile

    user = factory.SubFactory(UserFactory)
    bio = factory.Faker("text", max_nb_chars=200)
    discord_username = factory.Sequence(lambda n: f"discord_user_{n}")
    notifications_enabled = True
    theme = "dark"
