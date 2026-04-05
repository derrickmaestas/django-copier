import pytest

from apps.accounts.tests.factories import MembershipFactory, UserFactory
from apps.plans.models import Plan
from apps.plans.tests.factories import BucketFactory, PlanFactory


@pytest.mark.django_db
class TestPlanQuerySetForUser:
    """PlanQuerySet.for_user() returns plans visible through team membership."""

    def test_returns_plans_for_team_member(self):
        membership = MembershipFactory()
        plan = PlanFactory(team=membership.team)

        result = Plan.objects.for_user(membership.user)

        assert plan in result

    def test_excludes_plans_from_other_teams(self):
        user = UserFactory()
        plan = PlanFactory()  # belongs to a different team

        result = Plan.objects.for_user(user)

        assert plan not in result

    def test_no_duplicates_when_user_in_multiple_roles(self):
        """A user who is both owner and member should see each plan once."""
        membership = MembershipFactory()
        plan = PlanFactory(team=membership.team)
        # User also owns the team — could cause duplicate JOINs
        plan.team.owner = membership.user
        plan.team.save()

        result = Plan.objects.for_user(membership.user)

        assert list(result.filter(pk=plan.pk)).count(plan) == 1


@pytest.mark.django_db
class TestPlanQuerySetWithTaskCounts:
    """PlanQuerySet.with_task_counts() annotates total and completed counts."""

    def test_counts_tasks_across_buckets(self):
        plan = PlanFactory()
        bucket_a = BucketFactory(plan=plan, position=0)
        bucket_b = BucketFactory(plan=plan, position=1)

        from apps.tasks.tests.factories import TaskFactory

        TaskFactory(bucket=bucket_a)
        TaskFactory(bucket=bucket_b)

        annotated = Plan.objects.with_task_counts().get(pk=plan.pk)

        assert annotated.task_count == 2
        assert annotated.completed_task_count == 0

    def test_counts_completed_tasks(self):
        plan = PlanFactory()
        bucket = BucketFactory(plan=plan, position=0)

        from apps.tasks.tests.factories import TaskFactory

        TaskFactory(bucket=bucket, progress=100)
        TaskFactory(bucket=bucket, progress=50)

        annotated = Plan.objects.with_task_counts().get(pk=plan.pk)

        assert annotated.task_count == 2
        assert annotated.completed_task_count == 1

    def test_zero_counts_when_no_tasks(self):
        plan = PlanFactory()

        annotated = Plan.objects.with_task_counts().get(pk=plan.pk)

        assert annotated.task_count == 0
        assert annotated.completed_task_count == 0
