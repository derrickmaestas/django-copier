import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import TeamFactory, UserFactory
from apps.example.models import Item


class ItemFactory(DjangoModelFactory):
    class Meta:
        model = Item

    name = factory.Sequence(lambda n: f"Item {n}")
    description = factory.Faker("paragraph")
    team = factory.SubFactory(TeamFactory)
    created_by = factory.SubFactory(UserFactory)
