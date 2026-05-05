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


@pytest.mark.django_db
class TestPlanQuerySetSearch:
    """PlanQuerySet.search() runs Postgres FTS against the GeneratedField."""

    def test_matches_title(self):
        match = PlanFactory(title="Q3 Roadmap", description="")
        PlanFactory(title="Q4 Hiring Plan", description="")

        result = Plan.objects.search("roadmap")

        assert list(result) == [match]

    def test_matches_description(self):
        match = PlanFactory(title="Operations", description="weekly cadence with stakeholders")
        PlanFactory(title="Hiring", description="recruiter slate")

        result = Plan.objects.search("cadence")

        assert list(result) == [match]

    def test_unaccent_matches_diacritics(self):
        """`resume` (no accent) finds `résumé` thanks to english_unaccent."""
        match = PlanFactory(title="Résumé Reviewer", description="")

        result = Plan.objects.search("resume")

        assert list(result) == [match]

    def test_stemming_matches_regular_inflections(self):
        """The English stemmer reduces `migrations` and `migrated` to `migrat`."""
        match = PlanFactory(title="Migrations roadmap", description="")

        # `migrate` (different inflection) finds `migrations`
        assert match in list(Plan.objects.search("migrate"))

    def test_title_outranks_description(self):
        """Title is weighted A; description is weighted B (less the same number of hits)."""
        title_hit = PlanFactory(title="Onboarding overhaul", description="")
        desc_hit = PlanFactory(
            title="Quarterly planning",
            description="we should mention onboarding once",
        )

        ranked = list(Plan.objects.search("onboarding"))

        assert ranked.index(title_hit) < ranked.index(desc_hit)

    def test_empty_query_returns_empty(self):
        PlanFactory()
        assert list(Plan.objects.search("")) == []
        assert list(Plan.objects.search("   ")) == []

    def test_with_headline_annotates_snippet(self):
        PlanFactory(title="Onboarding", description="we ship onboarding emails on day one")

        plan = Plan.objects.search("onboarding", with_headline=True).first()

        assert plan is not None
        assert "<b>" in plan.headline
