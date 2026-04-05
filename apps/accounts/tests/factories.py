import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import Discipline, Membership, Team, User


class DisciplineFactory(DjangoModelFactory):
    class Meta:
        model = Discipline

    name = factory.Sequence(lambda n: f"Discipline {n}")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    employee_id = factory.Sequence(lambda n: 1000 + n)
    email = factory.LazyAttribute(lambda obj: f"{obj.employee_id}@example.com")
    display_name = factory.LazyAttribute(lambda obj: f"User {obj.employee_id}")
    division = ""
    organization = ""
    discipline = None
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
