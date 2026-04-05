from django.db import models


class PlanQuerySet(models.QuerySet):
    """Custom queryset for Plan with team-scoped access and annotation helpers."""

    def for_user(self, user):
        """Return plans visible to this user through team membership."""
        return self.filter(team__memberships__user=user).distinct()

    def with_task_counts(self):
        """Annotate each plan with total and completed task counts."""
        return self.annotate(
            task_count=models.Count(
                "buckets__tasks",
                distinct=True,
            ),
            completed_task_count=models.Count(
                "buckets__tasks",
                filter=models.Q(buckets__tasks__progress=100),
                distinct=True,
            ),
        )
