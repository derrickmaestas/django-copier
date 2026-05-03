"""django-filter FilterSets for the tasks API.

We define explicit FilterSets (rather than using `filterset_fields = [...]`
shorthand) so we can add the cross-model `plan` filter — a task doesn't
have a direct FK to Plan, but clients want to ask "all tasks in plan X"
without first looking up the plan's buckets.
"""

import django_filters

from apps.tasks.models import Task


class TaskFilter(django_filters.FilterSet):
    plan = django_filters.NumberFilter(field_name="bucket__plan_id")
    assignee = django_filters.NumberFilter(field_name="assignments__user_id")

    class Meta:
        model = Task
        fields = ["bucket", "priority", "progress", "plan", "assignee"]
