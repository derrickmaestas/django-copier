import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import Discipline, Membership, Team, User


class DisciplineFactory(DjangoModelFactory):
    class Meta:
        model = Discipline
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Discipline {n}")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("employee_id",)

    employee_id = factory.Sequence(lambda n: 10000 + n)
    email = factory.LazyAttribute(lambda o: f"user{o.employee_id}@example.com")
    display_name = factory.LazyAttribute(lambda o: f"User {o.employee_id}")


class TeamFactory(DjangoModelFactory):
    class Meta:
        model = Team
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Team {n}")
    owner = factory.SubFactory(UserFactory)


class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    team = factory.SubFactory(TeamFactory)
    user = factory.SubFactory(UserFactory)
    role = Membership.Role.MEMBER
