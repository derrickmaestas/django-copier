from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.tests.factories import (
    DisciplineFactory,
    MembershipFactory,
    TeamFactory,
    UserFactory,
)


class TestUser(TestCase):
    def test_employee_id_is_pk(self):
        user = UserFactory(employee_id=42)
        assert user.pk == 42

    def test_username_field(self):
        assert User.USERNAME_FIELD == "employee_id"

    def test_str(self):
        user = UserFactory(employee_id=12345)
        assert str(user) == "12345"


class TestDiscipline(TestCase):
    def test_str(self):
        discipline = DisciplineFactory(name="Design")
        assert str(discipline) == "Design"


class TestTeam(TestCase):
    def test_str(self):
        team = TeamFactory(name="Design")
        assert str(team) == "Design"


class TestMembership(TestCase):
    def test_str(self):
        membership = MembershipFactory()
        expected = (
            f"{membership.user.employee_id} — {membership.team.name} ({membership.role})"
        )
        assert str(membership) == expected
