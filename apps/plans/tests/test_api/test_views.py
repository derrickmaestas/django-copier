import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.models import Bucket, Plan
from apps.plans.tests.factories import BucketFactory, PlanFactory


@pytest.fixture
def member_client():
    """Return (client, user, team) where user is a member of team."""
    user = UserFactory()
    team = TeamFactory()
    MembershipFactory(team=team, user=user)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, team


@pytest.mark.django_db
class TestPlanList:
    """GET /api/v1/plans/ returns only plans on teams the user belongs to."""

    def test_lists_only_user_team_plans(self, member_client):
        client, user, team = member_client
        own = PlanFactory(team=team)
        other_team = TeamFactory()
        PlanFactory(team=other_team)

        response = client.get("/api/v1/plans/")

        assert response.status_code == 200
        ids = {row["id"] for row in response.data["results"]}
        assert ids == {own.pk}

    def test_unauthenticated_returns_401(self):
        response = APIClient().get("/api/v1/plans/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestPlanRetrieve:
    """GET /api/v1/plans/{id}/ returns 404 for non-members (no existence leak)."""

    def test_member_can_retrieve(self, member_client):
        client, user, team = member_client
        plan = PlanFactory(team=team)

        response = client.get(f"/api/v1/plans/{plan.pk}/")

        assert response.status_code == 200
        assert response.data["title"] == plan.title

    def test_non_member_gets_404_not_403(self, member_client):
        client, user, team = member_client
        other_plan = PlanFactory(team=TeamFactory())

        response = client.get(f"/api/v1/plans/{other_plan.pk}/")

        assert response.status_code == 404


@pytest.mark.django_db
class TestPlanCreate:
    """POST /api/v1/plans/ stamps created_by from the request user."""

    def test_create_stamps_created_by(self, member_client):
        client, user, team = member_client

        response = client.post(
            "/api/v1/plans/",
            {"title": "Q3 Roadmap", "team": team.pk},
            format="json",
        )

        assert response.status_code == 201, response.data
        plan = Plan.objects.get(pk=response.data["id"])
        assert plan.created_by == user
        assert plan.title == "Q3 Roadmap"

    def test_client_supplied_created_by_is_ignored(self, member_client):
        """Even if a client posts created_by, the server overwrites it."""
        client, user, team = member_client
        intruder = UserFactory()

        response = client.post(
            "/api/v1/plans/",
            {
                "title": "Spoof attempt",
                "team": team.pk,
                "created_by": intruder.pk,
            },
            format="json",
        )

        assert response.status_code == 201
        plan = Plan.objects.get(pk=response.data["id"])
        assert plan.created_by == user


@pytest.mark.django_db
class TestPlanUpdateDelete:
    """Members can update and delete plans on their teams; non-members 404."""

    def test_member_can_update(self, member_client):
        client, user, team = member_client
        plan = PlanFactory(team=team, title="Old")

        response = client.patch(
            f"/api/v1/plans/{plan.pk}/", {"title": "New"}, format="json"
        )

        assert response.status_code == 200
        plan.refresh_from_db()
        assert plan.title == "New"

    def test_non_member_cannot_update(self, member_client):
        client, _, _ = member_client
        other_plan = PlanFactory(team=TeamFactory())

        response = client.patch(
            f"/api/v1/plans/{other_plan.pk}/", {"title": "Hack"}, format="json"
        )

        assert response.status_code == 404

    def test_member_can_delete(self, member_client):
        client, user, team = member_client
        plan = PlanFactory(team=team)

        response = client.delete(f"/api/v1/plans/{plan.pk}/")

        assert response.status_code == 204
        assert not Plan.objects.filter(pk=plan.pk).exists()


@pytest.mark.django_db
class TestBucketCreate:
    """POST /api/v1/buckets/ assigns the next position automatically."""

    def test_position_auto_assigned(self, member_client):
        client, user, team = member_client
        plan = PlanFactory(team=team)
        BucketFactory(plan=plan, position=1)
        BucketFactory(plan=plan, position=2)

        response = client.post(
            "/api/v1/buckets/",
            {"plan": plan.pk, "title": "Done"},
            format="json",
        )

        assert response.status_code == 201
        bucket = Bucket.objects.get(pk=response.data["id"])
        assert bucket.position == 3

    def test_filter_by_plan(self, member_client):
        client, user, team = member_client
        plan_a = PlanFactory(team=team)
        plan_b = PlanFactory(team=team)
        BucketFactory(plan=plan_a, position=1)
        BucketFactory(plan=plan_a, position=2)
        BucketFactory(plan=plan_b, position=1)

        response = client.get(f"/api/v1/buckets/?plan={plan_a.pk}")

        assert response.status_code == 200
        assert response.data["count"] == 2
