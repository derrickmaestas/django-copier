"""Hard caps on the query count of the unified-search hot paths.

The HTML view at `/search/` and the JSON view at `/api/v1/search/` each
run two FTS branches (Plans and Tasks) plus the team-scoping JOINs.
This file pins the exact total count for both paths under a non-trivial
dataset; if a future refactor introduces a per-row lookup (rendering
the parent plan label next to each task hit, walking task.assignees in
the snippet, etc.) the counts go up and the test goes red.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.tests.factories import CommentFactory, TaskFactory


@pytest.fixture
def member_with_searchable_data(client, django_assert_num_queries):
    """A user logged in to a team with several FTS hits across plans and tasks."""
    user = UserFactory()
    user.set_password("pw")
    user.save()
    team = TeamFactory()
    MembershipFactory(team=team, user=user)

    # 5 plans, 5 buckets, 15 tasks (3 per bucket) — all matching the query
    # term in description so the FTS branches return hits.
    for _ in range(5):
        plan = PlanFactory(team=team, description="onboarding overhaul")
        bucket = BucketFactory(plan=plan)
        for _ in range(3):
            task = TaskFactory(bucket=bucket, description="onboarding flow")
            CommentFactory(task=task, body="more onboarding context")

    client.force_login(user)
    return client, django_assert_num_queries


@pytest.mark.django_db
class TestSearchViewQueryCount:
    """`/search/?q=onboarding` runs at constant query count over the dataset."""

    def test_constant_query_count(self, member_with_searchable_data):
        """Four queries: session, current user, the Plan FTS, the Task FTS.

        Each FTS branch is one query — the team-scoping `for_user()` filter
        folds into the SELECT as a JOIN, and `select_related("bucket",
        "bucket__plan")` keeps the parent-plan label that's rendered next
        to each task hit out of the per-row loop.
        """
        client, django_assert_num_queries = member_with_searchable_data
        with django_assert_num_queries(4):
            response = client.get("/search/", {"q": "onboarding"})
        assert response.status_code == 200

    def test_empty_query_skips_fts(self, member_with_searchable_data):
        """An empty query must NOT run the FTS branches — just render the prompt."""
        client, django_assert_num_queries = member_with_searchable_data
        # Two queries: session + user; no FTS work because q is empty.
        with django_assert_num_queries(2):
            response = client.get("/search/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestSearchAPIQueryCount:
    """`/api/v1/search/?q=onboarding` is the API equivalent."""

    def test_constant_query_count(self, django_assert_num_queries):
        user = UserFactory()
        team = TeamFactory()
        MembershipFactory(team=team, user=user)
        for _ in range(5):
            plan = PlanFactory(team=team, description="onboarding overhaul")
            bucket = BucketFactory(plan=plan)
            for _ in range(3):
                task = TaskFactory(bucket=bucket, description="onboarding flow")
                CommentFactory(task=task, body="more onboarding context")

        client = APIClient()
        client.force_authenticate(user=user)

        # Two queries: the Plan FTS + the Task FTS. APIClient.force_authenticate
        # bypasses session/user lookups.
        with django_assert_num_queries(2):
            response = client.get("/api/v1/search/?q=onboarding")
        assert response.status_code == 200
