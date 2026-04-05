from django.db import models
from django.utils import timezone


class TaskQuerySet(models.QuerySet):
    """Custom queryset for Task with scoping, filtering, and annotation helpers."""

    def for_user(self, user):
        """Return tasks assigned to this user."""
        return self.filter(assignments__user=user).distinct()

    def overdue(self):
        """Return incomplete tasks past their due date."""
        return self.filter(
            due_date__lt=timezone.now().date(),
            progress__lt=100,
        )

    def with_checklist_counts(self):
        """Annotate each task with total and completed checklist item counts."""
        return self.annotate(
            checklist_total=models.Count("checklist_items", distinct=True),
            checklist_done=models.Count(
                "checklist_items",
                filter=models.Q(checklist_items__is_completed=True),
                distinct=True,
            ),
        )

    def search(self, query):
        """Basic title/description search. Will be replaced with FTS in Chapter 14."""
        return self.filter(
            models.Q(title__icontains=query) | models.Q(description__icontains=query)
        )
