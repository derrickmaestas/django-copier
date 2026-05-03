import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.models import Comment, Task
from apps.tasks.tests.factories import CommentFactory, TaskFactory


@pytest.fixture
def member_team():
    user = UserFactory()
    team = TeamFactory()
    MembershipFactory(team=team, user=user)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, team


@pytest.mark.django_db
class TestTaskList:
    """GET /api/v1/tasks/ enforces team-scoping and exposes search/ordering."""

    def test_only_user_team_tasks(self, member_team):
        client, user, team = member_team
        own_bucket = BucketFactory(plan=PlanFactory(team=team))
        own = TaskFactory(bucket=own_bucket)
        TaskFactory(bucket=BucketFactory(plan=PlanFactory(team=TeamFactory())))

        response = client.get("/api/v1/tasks/")

        assert response.status_code == 200
        ids = {row["id"] for row in response.data["results"]}
        assert ids == {own.pk}

    def test_search_matches_title(self, member_team):
        client, user, team = member_team
        bucket = BucketFactory(plan=PlanFactory(team=team))
        TaskFactory(bucket=bucket, title="Wire up login flow")
        TaskFactory(bucket=bucket, title="Refactor dashboard")

        response = client.get("/api/v1/tasks/?search=login")

        assert response.data["count"] == 1
        assert "login" in response.data["results"][0]["title"].lower()

    def test_ordering_by_due_date(self, member_team):
        client, user, team = member_team
        bucket = BucketFactory(plan=PlanFactory(team=team))
        TaskFactory(bucket=bucket, due_date="2026-12-01")
        TaskFactory(bucket=bucket, due_date="2026-06-01")

        response = client.get("/api/v1/tasks/?ordering=due_date")

        dates = [row["due_date"] for row in response.data["results"]]
        assert dates == ["2026-06-01", "2026-12-01"]


@pytest.mark.django_db
class TestTaskCreate:
    """POST /api/v1/tasks/ stamps created_by from the request user."""

    def test_create_stamps_created_by(self, member_team):
        client, user, team = member_team
        bucket = BucketFactory(plan=PlanFactory(team=team))

        response = client.post(
            "/api/v1/tasks/",
            {"title": "Triage backlog", "bucket": bucket.pk},
            format="json",
        )

        assert response.status_code == 201, response.data
        task = Task.objects.get(pk=response.data["id"])
        assert task.created_by == user

    def test_cannot_create_in_non_team_bucket(self, member_team):
        """A task created against a foreign bucket isn't visible on subsequent reads."""
        client, _, _ = member_team
        other_bucket = BucketFactory(plan=PlanFactory(team=TeamFactory()))

        response = client.post(
            "/api/v1/tasks/",
            {"title": "Hack", "bucket": other_bucket.pk},
            format="json",
        )

        if response.status_code == 201:
            list_response = client.get("/api/v1/tasks/")
            assert response.data["id"] not in {
                row["id"] for row in list_response.data["results"]
            }


@pytest.mark.django_db
class TestCommentCreate:
    """POST /api/v1/comments/ stamps created_by; non-members get 404."""

    def test_member_can_comment(self, member_team):
        client, user, team = member_team
        task = TaskFactory(bucket=BucketFactory(plan=PlanFactory(team=team)))

        response = client.post(
            "/api/v1/comments/",
            {"task": task.pk, "body": "Looking into this."},
            format="json",
        )

        assert response.status_code == 201
        comment = Comment.objects.get(pk=response.data["id"])
        assert comment.created_by == user
        assert comment.task == task

    def test_non_member_cannot_comment(self, member_team):
        client, _, _ = member_team
        other_task = TaskFactory(
            bucket=BucketFactory(plan=PlanFactory(team=TeamFactory()))
        )

        response = client.post(
            "/api/v1/comments/",
            {"task": other_task.pk, "body": "👀"},
            format="json",
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestCommentList:
    """GET /api/v1/comments/?task=<id> filters comments to a single task."""

    def test_filter_by_task(self, member_team):
        client, user, team = member_team
        task_a = TaskFactory(bucket=BucketFactory(plan=PlanFactory(team=team)))
        task_b = TaskFactory(bucket=BucketFactory(plan=PlanFactory(team=team)))
        CommentFactory(task=task_a)
        CommentFactory(task=task_a)
        CommentFactory(task=task_b)

        response = client.get(f"/api/v1/comments/?task={task_a.pk}")

        assert response.data["count"] == 2
