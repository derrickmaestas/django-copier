import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Membership
from apps.accounts.tests.factories import (
    MembershipFactory,
    TeamFactory,
    UserFactory,
)
from apps.plans.tests.factories import PlanFactory


@pytest.fixture
def member_client():
    user = UserFactory()
    team = TeamFactory()
    MembershipFactory(team=team, user=user, role=Membership.Role.MEMBER)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, team


@pytest.fixture
def owner_client():
    user = UserFactory()
    team = TeamFactory()
    MembershipFactory(team=team, user=user, role=Membership.Role.OWNER)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, team


@pytest.fixture
def admin_client():
    user = UserFactory()
    team = TeamFactory()
    MembershipFactory(team=team, user=user, role=Membership.Role.ADMIN)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, team


@pytest.mark.django_db
class TestPlanReadOpenToAllMembers:
    """SAFE_METHODS pass through with just IsAuthenticated."""

    def test_member_can_list(self, member_client):
        client, user, team = member_client
        PlanFactory(team=team)
        assert client.get("/api/v1/plans/").status_code == 200

    def test_member_can_retrieve(self, member_client):
        client, user, team = member_client
        plan = PlanFactory(team=team)
        assert client.get(f"/api/v1/plans/{plan.pk}/").status_code == 200


@pytest.mark.django_db
class TestPlanDeletionPrivileged:
    """Only OWNER and ADMIN can delete a plan."""

    def test_member_cannot_delete(self, member_client):
        client, user, team = member_client
        plan = PlanFactory(team=team)

        response = client.delete(f"/api/v1/plans/{plan.pk}/")

        assert response.status_code == 403

    def test_owner_can_delete(self, owner_client):
        client, user, team = owner_client
        plan = PlanFactory(team=team)

        response = client.delete(f"/api/v1/plans/{plan.pk}/")

        assert response.status_code == 204

    def test_admin_can_delete(self, admin_client):
        client, user, team = admin_client
        plan = PlanFactory(team=team)

        response = client.delete(f"/api/v1/plans/{plan.pk}/")

        assert response.status_code == 204


@pytest.mark.django_db
class TestPlanVisibilityPrivileged:
    """Visibility changes require OWNER or ADMIN; other fields don't."""

    def test_member_can_update_title(self, member_client):
        client, user, team = member_client
        plan = PlanFactory(team=team, title="Old")

        response = client.patch(
            f"/api/v1/plans/{plan.pk}/", {"title": "New"}, format="json"
        )

        assert response.status_code == 200

    def test_member_cannot_change_visibility(self, member_client):
        client, user, team = member_client
        plan = PlanFactory(team=team)

        response = client.patch(
            f"/api/v1/plans/{plan.pk}/", {"visibility": "public"}, format="json"
        )

        assert response.status_code == 403

    def test_owner_can_change_visibility(self, owner_client):
        client, user, team = owner_client
        plan = PlanFactory(team=team)

        response = client.patch(
            f"/api/v1/plans/{plan.pk}/", {"visibility": "public"}, format="json"
        )

        assert response.status_code == 200


@pytest.mark.django_db
class TestPlanNonMemberStill404:
    """Non-members can't reach a plan at all — the queryset filter is still primary."""

    def test_non_member_delete_is_404_not_403(self, member_client):
        """The queryset hides the plan first; the permission class never sees it."""
        client, _, _ = member_client
        # Plan on a team this user isn't a member of
        other_plan = PlanFactory(team=TeamFactory())

        response = client.delete(f"/api/v1/plans/{other_plan.pk}/")

        assert response.status_code == 404
