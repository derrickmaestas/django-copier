import pytest
from django.urls import reverse

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.models import Bucket, Plan
from apps.plans.tests.factories import BucketFactory, PlanFactory


@pytest.fixture
def member_and_plan(db):
    user = UserFactory()
    plan = PlanFactory()
    MembershipFactory(team=plan.team, user=user)
    return user, plan


@pytest.mark.django_db
class TestPlanListView:
    def test_only_lists_plans_user_can_see(self, client):
        user = UserFactory()
        my_plan = PlanFactory()
        MembershipFactory(team=my_plan.team, user=user)
        PlanFactory()  # someone else's plan

        client.force_login(user)
        response = client.get(reverse("plans:plan-list"))

        assert list(response.context["plans"]) == [my_plan]

    def test_redirects_anonymous_to_login(self, client):
        response = client.get(reverse("plans:plan-list"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url


@pytest.mark.django_db
class TestPlanDetailView:
    def test_member_can_view(self, client, member_and_plan):
        user, plan = member_and_plan
        client.force_login(user)
        response = client.get(reverse("plans:plan-detail", kwargs={"pk": plan.pk}))
        assert response.status_code == 200

    def test_non_member_gets_404(self, client):
        user = UserFactory()
        plan = PlanFactory()  # user is NOT in this plan's team
        client.force_login(user)
        response = client.get(reverse("plans:plan-detail", kwargs={"pk": plan.pk}))
        assert response.status_code == 404


@pytest.mark.django_db
class TestPlanCreateView:
    def test_form_valid_sets_created_by_and_owner(self, client):
        user = UserFactory()
        team = TeamFactory()
        MembershipFactory(team=team, user=user)
        client.force_login(user)

        response = client.post(
            reverse("plans:plan-create"),
            {
                "title": "My new plan",
                "description": "",
                "team": team.pk,
                "visibility": Plan.Visibility.PRIVATE,
            },
        )

        plan = Plan.objects.get(title="My new plan")
        assert plan.created_by == user
        assert plan.owner == user
        assert response.status_code == 302
        assert response.url == reverse("plans:plan-detail", kwargs={"pk": plan.pk})


@pytest.mark.django_db
class TestPlanUpdateView:
    def test_non_member_cannot_update(self, client):
        user = UserFactory()
        plan = PlanFactory()
        client.force_login(user)
        response = client.post(
            reverse("plans:plan-update", kwargs={"pk": plan.pk}),
            {"title": "hijacked", "description": "", "visibility": Plan.Visibility.PRIVATE},
        )
        assert response.status_code == 404
        plan.refresh_from_db()
        assert plan.title != "hijacked"


@pytest.mark.django_db
class TestPlanDeleteView:
    def test_non_member_cannot_delete(self, client):
        user = UserFactory()
        plan = PlanFactory()
        client.force_login(user)
        response = client.post(reverse("plans:plan-delete", kwargs={"pk": plan.pk}))
        assert response.status_code == 404
        assert Plan.objects.filter(pk=plan.pk).exists()


@pytest.mark.django_db
class TestBucketCreateView:
    def test_member_creates_bucket_with_auto_position(self, client, member_and_plan):
        user, plan = member_and_plan
        BucketFactory(plan=plan, position=3)  # existing bucket
        client.force_login(user)

        response = client.post(
            reverse("plans:bucket-create", kwargs={"plan_pk": plan.pk}),
            {"title": "  In review  "},  # whitespace gets stripped
        )

        bucket = Bucket.objects.get(plan=plan, title="In review")
        assert bucket.position == 4
        assert response.status_code == 302
        assert response.url == reverse("plans:plan-detail", kwargs={"pk": plan.pk})

    def test_non_member_cannot_create(self, client):
        user = UserFactory()
        plan = PlanFactory()
        client.force_login(user)
        response = client.get(
            reverse("plans:bucket-create", kwargs={"plan_pk": plan.pk}),
        )
        assert response.status_code == 404

    def test_blank_title_rejected(self, client, member_and_plan):
        user, plan = member_and_plan
        client.force_login(user)
        response = client.post(
            reverse("plans:bucket-create", kwargs={"plan_pk": plan.pk}),
            {"title": "   "},
        )
        assert response.status_code == 200
        assert response.context["form"].errors["title"]
        assert not Bucket.objects.filter(plan=plan).exists()


@pytest.mark.django_db
class TestBucketUpdateView:
    def test_non_member_cannot_update(self, client):
        user = UserFactory()
        bucket = BucketFactory()
        client.force_login(user)
        response = client.post(
            reverse("plans:bucket-update", kwargs={"pk": bucket.pk}),
            {"title": "hijacked"},
        )
        assert response.status_code == 404
        bucket.refresh_from_db()
        assert bucket.title != "hijacked"


@pytest.mark.django_db
class TestBucketDeleteView:
    def test_non_member_cannot_delete(self, client):
        user = UserFactory()
        bucket = BucketFactory()
        client.force_login(user)
        response = client.post(reverse("plans:bucket-delete", kwargs={"pk": bucket.pk}))
        assert response.status_code == 404
        assert Bucket.objects.filter(pk=bucket.pk).exists()
