"""Hard caps on the query count of the tasks hot paths.

Pattern matches `apps/plans/tests/test_performance.py` — the dataset
is non-trivial so a hidden N+1 actually shows up, and counts are
exact so both regressions and accidental drops trip the test.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.tests.factories import (
    AssignmentFactory,
    CommentFactory,
    TaskFactory,
)


@pytest.fixture
def member_with_tasks(django_assert_num_queries):
    """Returns (api_client, user, plan, django_assert_num_queries) and
    seeds 15 tasks across 3 buckets, each with 3 assignees."""
    user = UserFactory()
    team = TeamFactory()
    MembershipFactory(team=team, user=user)
    plan = PlanFactory(team=team)
    other_users = [UserFactory() for _ in range(3)]

    for bucket_pos in range(3):
        bucket = BucketFactory(plan=plan, position=bucket_pos)
        for _ in range(5):
            task = TaskFactory(bucket=bucket)
            for assignee in other_users:
                AssignmentFactory(task=task, user=assignee)

    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, plan, django_assert_num_queries


@pytest.mark.django_db
class TestTaskListAPIQueryCount:
    """`/api/v1/tasks/` is the highest-traffic API path; lock its query budget."""

    def test_constant_query_count(self, member_with_tasks):
        """Three queries: pagination COUNT, the SELECT (with select_related
        rolled into JOINs), and the assignees prefetch.

        APIClient.force_authenticate skips session/user lookups, so the
        budget here is lower than the HTML-side counts in the plans tests.
        """
        client, _, _, django_assert_num_queries = member_with_tasks
        with django_assert_num_queries(3):
            response = client.get("/api/v1/tasks/")
        assert response.status_code == 200

    def test_count_unchanged_when_dataset_doubles(self, member_with_tasks):
        """The N+1 detector — same query count regardless of how many tasks come back."""
        client, _, plan, django_assert_num_queries = member_with_tasks
        for bucket in plan.buckets.all():
            for _ in range(5):
                TaskFactory(bucket=bucket)

        with django_assert_num_queries(3):
            response = client.get("/api/v1/tasks/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestTaskDetailViewQueryCount:
    """`/tasks/<id>/` displays a single task with its checklist and comments."""

    def test_constant_query_count(self, client, django_assert_num_queries):
        user = UserFactory()
        user.set_password("pw")
        user.save()
        team = TeamFactory()
        MembershipFactory(team=team, user=user)
        bucket = BucketFactory(plan=PlanFactory(team=team))
        task = TaskFactory(bucket=bucket)
        # Sibling rows that the page renders.
        for _ in range(5):
            CommentFactory(task=task, created_by=user)

        client.force_login(user)
        # Eight queries: session lookup, current user, the Task SELECT (with
        # for_user JOIN), and five prefetches — checklist_items, assignees
        # (M2M through-table), attachments, comments (one prefetch covers
        # the select_related on created_by inside the Prefetch).
        with django_assert_num_queries(8):
            response = client.get(f"/tasks/{task.pk}/")
        assert response.status_code == 200
