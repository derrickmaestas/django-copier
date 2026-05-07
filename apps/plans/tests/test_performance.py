"""Hard caps on the query count of the plans hot paths.

Each test seeds a non-trivial dataset (multiple buckets, multiple tasks
per bucket, multiple assignees per task) and asserts the view renders
in *exactly* N queries — no more, no fewer. Exact counts catch both
N+1 regressions (the count goes up when the dataset grows) and silent
behavior changes (the count drops because a feature was accidentally
removed). When a count legitimately changes, update the assertion in
the same commit and explain why in the message.

The dataset is *deliberately* non-trivial: an N+1 with one bucket and
one task looks identical to a constant-time view.
"""

import pytest

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.tests.factories import (
    AssignmentFactory,
    ChecklistItemFactory,
    TaskFactory,
)


@pytest.fixture
def member_with_full_plan(client, django_assert_num_queries):
    """A user logged in to a plan with 3 buckets × 5 tasks × 3 assignees + checklist items."""
    user = UserFactory()
    user.set_password("pw")
    user.save()
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
            for item_pos in range(2):
                ChecklistItemFactory(task=task, position=item_pos)

    client.force_login(user)
    return client, plan, django_assert_num_queries


@pytest.mark.django_db
class TestPlanDetailQueryCount:
    """The kanban board renders 3 buckets × 5 tasks at constant query count."""

    def test_kanban_constant_query_count(self, member_with_full_plan):
        """The kanban renders in a fixed query budget regardless of dataset size.

        Five queries: session lookup, current user, the Plan-with-for_user
        scoping, the buckets prefetch, the tasks prefetch. If this number
        ticks up, suspect one of:

        - A `.count()` or `.exists()` on a NON-prefetched relation — Django's
          RelatedManager is prefetch-aware, but only when the relation
          itself was named in `prefetch_related`.
        - A new template loop that walks an unrelated relation
          (`task.assignees`, `task.labels`) without `prefetch_related`.
        - A view-level annotation that adds a subquery per row.
        """
        client, plan, django_assert_num_queries = member_with_full_plan
        with django_assert_num_queries(5):
            response = client.get(f"/plans/{plan.pk}/")
        assert response.status_code == 200

    def test_kanban_query_count_unchanged_when_dataset_grows(
        self, member_with_full_plan
    ):
        """Doubling the dataset does NOT increase the query count — the canonical
        N+1 detector. If this fails the prefetch chain has a hole somewhere."""
        client, plan, django_assert_num_queries = member_with_full_plan
        # Seed a second batch of identical size.
        for bucket in plan.buckets.all():
            for _ in range(5):
                TaskFactory(bucket=bucket)

        with django_assert_num_queries(5):
            response = client.get(f"/plans/{plan.pk}/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestPlanListQueryCount:
    """The plan list with task-count annotations runs at constant query count."""

    def test_plan_list_constant_query_count(self, client, django_assert_num_queries):
        user = UserFactory()
        user.set_password("pw")
        user.save()
        team = TeamFactory()
        MembershipFactory(team=team, user=user)
        for _ in range(5):
            plan = PlanFactory(team=team)
            bucket = BucketFactory(plan=plan)
            for _ in range(3):
                TaskFactory(bucket=bucket)

        client.force_login(user)
        # Three queries: session lookup, current user, plans-with-task-counts
        # (a single SELECT with the COUNT subqueries inlined as annotations).
        with django_assert_num_queries(3):
            response = client.get("/plans/")
        assert response.status_code == 200
