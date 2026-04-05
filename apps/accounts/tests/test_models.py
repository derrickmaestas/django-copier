from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from apps.accounts.models import Membership, Team, User
from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory


class TestUser(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            username="jane",
            email="jane@example.com",
            password="testpass123",  # noqa: S106
            employee_id=1001,
        )
        assert user.pk is not None
        assert user.username == "jane"
        assert user.check_password("testpass123")
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123",  # noqa: S106
            employee_id=9999,
        )
        assert admin.is_staff
        assert admin.is_superuser

    def test_employee_id_unique(self):
        UserFactory(employee_id=42)
        with self.assertRaises(IntegrityError):
            UserFactory(employee_id=42)

    def test_str(self):
        user = UserFactory(username="janedoe")
        assert str(user) == "janedoe"

    def test_default_ordering(self):
        UserFactory(username="charlie")
        UserFactory(username="alice")
        UserFactory(username="bob")
        usernames = list(User.objects.values_list("username", flat=True))
        assert usernames == ["alice", "bob", "charlie"]

    def test_display_name_optional(self):
        user = UserFactory(display_name="")
        assert user.display_name == ""

    def test_is_manager_default_false(self):
        user = UserFactory()
        assert user.is_manager is False

    def test_profile_fields_optional(self):
        user = UserFactory(division="", organization="", team="")
        assert user.division == ""
        assert user.organization == ""
        assert user.team == ""

    def test_factory_creates_valid_user(self):
        user = UserFactory()
        assert user.pk is not None
        assert user.employee_id is not None

    def test_has_timestamps(self):
        user = UserFactory()
        assert user.created_at is not None
        assert user.modified_at is not None


class TestTeam(TestCase):
    def test_create_team(self):
        owner = UserFactory()
        team = Team.objects.create(name="Engineering", owner=owner)
        assert team.pk is not None
        assert team.name == "Engineering"
        assert team.owner == owner

    def test_str(self):
        team = TeamFactory(name="Design")
        assert str(team) == "Design"

    def test_name_unique(self):
        TeamFactory(name="Marketing")
        with self.assertRaises(IntegrityError):
            TeamFactory(name="Marketing")

    def test_owner_protect_on_delete(self):
        """Deleting a user who owns a team should be prevented."""
        team = TeamFactory()
        with self.assertRaises(ProtectedError):
            team.owner.delete()

    def test_has_timestamps(self):
        team = TeamFactory()
        assert team.created_at is not None
        assert team.modified_at is not None

    def test_factory_creates_valid_team(self):
        team = TeamFactory()
        assert team.pk is not None
        assert team.owner is not None


class TestMembership(TestCase):
    def test_create_membership(self):
        membership = MembershipFactory()
        assert membership.pk is not None
        assert membership.role == Membership.Role.MEMBER

    def test_role_choices(self):
        assert Membership.Role.OWNER == "owner"
        assert Membership.Role.ADMIN == "admin"
        assert Membership.Role.MEMBER == "member"

    def test_unique_user_per_team(self):
        membership = MembershipFactory()
        with self.assertRaises(IntegrityError):
            MembershipFactory(team=membership.team, user=membership.user)

    def test_user_cascade_deletes_membership(self):
        """Deleting a non-owner user removes their memberships."""
        team = TeamFactory()
        user = UserFactory()
        MembershipFactory(team=team, user=user)
        user_pk = user.pk
        assert Membership.objects.filter(user_id=user_pk).count() == 1
        user.delete()
        assert Membership.objects.filter(user_id=user_pk).count() == 0

    def test_team_cascade_deletes_memberships(self):
        membership = MembershipFactory()
        team_pk = membership.team.pk
        assert Membership.objects.filter(team_id=team_pk).count() == 1
        membership.team.delete()
        assert Membership.objects.filter(team_id=team_pk).count() == 0

    def test_str(self):
        membership = MembershipFactory()
        expected = f"{membership.user.username} — {membership.team.name} ({membership.role})"
        assert str(membership) == expected

    def test_has_timestamps(self):
        membership = MembershipFactory()
        assert membership.created_at is not None
        assert membership.modified_at is not None

    def test_default_ordering(self):
        team = TeamFactory()
        MembershipFactory(team=team, user=UserFactory(username="zara"))
        MembershipFactory(team=team, user=UserFactory(username="alice"))
        members = list(
            Membership.objects.filter(team=team).values_list("user__username", flat=True)
        )
        assert members == ["alice", "zara"]
