from django import forms

from apps.accounts.models import Team

from .models import Bucket, Plan


class PlanForm(forms.ModelForm):
    """Form for creating or editing a Plan.

    The `team` queryset is restricted to teams the user is a member of —
    without this, anyone could submit an arbitrary `team_id` and have a
    plan attached to a team they don't belong to.
    """

    class Meta:
        model = Plan
        fields = ["title", "description", "team", "visibility"]

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = Team.objects.filter(memberships__user=user).distinct()


class BucketForm(forms.ModelForm):
    """Form for creating or editing a Bucket within a known Plan.

    The plan is supplied by the view (resolved from the URL), so only
    the title is exposed to the user. Position is auto-set on create.
    """

    class Meta:
        model = Bucket
        fields = ["title"]
