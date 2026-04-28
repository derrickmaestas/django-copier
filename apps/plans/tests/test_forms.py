import pytest

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.plans.forms import PlanForm
from apps.plans.models import Plan


@pytest.mark.django_db
class TestPlanForm:
    def test_team_choices_limited_to_user_memberships(self):
        user = UserFactory()
        my_team = TeamFactory()
        MembershipFactory(team=my_team, user=user)
        TeamFactory()  # team the user does NOT belong to

        form = PlanForm(user=user)

        assert list(form.fields["team"].queryset) == [my_team]

    def test_cannot_submit_team_user_is_not_in(self):
        user = UserFactory()
        outside_team = TeamFactory()  # user is not a member

        form = PlanForm(
            data={
                "title": "Sneaky plan",
                "description": "",
                "team": outside_team.pk,
                "visibility": Plan.Visibility.PRIVATE,
            },
            user=user,
        )

        assert not form.is_valid()
        assert "team" in form.errors
