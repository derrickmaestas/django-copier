import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import Membership, Team, User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    employee_id = factory.Sequence(lambda n: 1000 + n)
    display_name = factory.LazyAttribute(lambda obj: obj.username.title())
    division = ""
    organization = ""
    team = ""
    is_manager = False


class TeamFactory(DjangoModelFactory):
    class Meta:
        model = Team

    name = factory.Sequence(lambda n: f"Team {n}")
    owner = factory.SubFactory(UserFactory)


class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    team = factory.SubFactory(TeamFactory)
    user = factory.SubFactory(UserFactory)
    role = Membership.Role.MEMBER
