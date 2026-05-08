import pytest

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory


@pytest.mark.django_db
class TestUser:
    def test_str_returns_employee_id(self):
        user = UserFactory(employee_id=42)
        assert str(user) == "42"


@pytest.mark.django_db
class TestTeam:
    def test_str_returns_name(self):
        team = TeamFactory(name="Platform")
        assert str(team) == "Platform"


@pytest.mark.django_db
class TestMembership:
    def test_str_includes_employee_id_team_and_role(self):
        membership = MembershipFactory(
            user=UserFactory(employee_id=99),
            team=TeamFactory(name="Eng"),
        )
        assert "99" in str(membership)
        assert "Eng" in str(membership)
        assert "member" in str(membership)
