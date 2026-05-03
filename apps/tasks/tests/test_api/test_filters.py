import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.models import Task
from apps.tasks.tests.factories import AssignmentFactory, TaskFactory


@pytest.fixture
def member_team():
    user = UserFactory()
    team = TeamFactory()
    MembershipFactory(team=team, user=user)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, team


@pytest.mark.django_db
class TestTaskFilter:
    """TaskFilter narrows the list endpoint via query parameters."""

    def test_filter_by_plan(self, member_team):
        """`?plan=<id>` walks bucket→plan_id under the hood."""
        client, user, team = member_team
        plan_a = PlanFactory(team=team)
        plan_b = PlanFactory(team=team)
        TaskFactory(bucket=BucketFactory(plan=plan_a))
        TaskFactory(bucket=BucketFactory(plan=plan_a))
        TaskFactory(bucket=BucketFactory(plan=plan_b))

        response = client.get(f"/api/v1/tasks/?plan={plan_a.pk}")

        assert response.data["count"] == 2

    def test_filter_by_priority(self, member_team):
        client, user, team = member_team
        bucket = BucketFactory(plan=PlanFactory(team=team))
        TaskFactory(bucket=bucket, priority=Task.Priority.URGENT)
        TaskFactory(bucket=bucket, priority=Task.Priority.LOW)

        response = client.get(f"/api/v1/tasks/?priority={Task.Priority.URGENT}")

        assert response.data["count"] == 1

    def test_filter_by_progress(self, member_team):
        client, user, team = member_team
        bucket = BucketFactory(plan=PlanFactory(team=team))
        TaskFactory(bucket=bucket, progress=Task.Progress.COMPLETED)
        TaskFactory(bucket=bucket, progress=Task.Progress.NOT_STARTED)

        response = client.get(f"/api/v1/tasks/?progress={Task.Progress.COMPLETED}")

        assert response.data["count"] == 1

    def test_filter_by_assignee(self, member_team):
        """`?assignee=<employee_id>` walks Task.assignments.user_id."""
        client, user, team = member_team
        bucket = BucketFactory(plan=PlanFactory(team=team))
        assigned = TaskFactory(bucket=bucket)
        AssignmentFactory(task=assigned, user=user)
        TaskFactory(bucket=bucket)

        response = client.get(f"/api/v1/tasks/?assignee={user.pk}")

        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == assigned.pk
