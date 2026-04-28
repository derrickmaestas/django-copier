from django.db import models
from django.utils import timezone

from apps.core.querysets import OrderedQuerySet


class TaskQuerySet(models.QuerySet):
    """Custom queryset for Task with scoping, filtering, and annotation helpers."""

    def for_user(self, user):
        """Return tasks in plans visible to this user through team membership."""
        return self.filter(bucket__plan__team__memberships__user=user).distinct()

    def assigned_to(self, user):
        """Return tasks the user is explicitly assigned to.

        Distinct from `for_user(user)` — assignment is the narrower set:
        a user might be a team member of a plan but only assigned to a
        few of its tasks.
        """
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


class LabelQuerySet(models.QuerySet):
    """Custom queryset for Label with team-scoped access."""

    def for_user(self, user):
        return self.filter(plan__team__memberships__user=user).distinct()


class ChecklistItemQuerySet(OrderedQuerySet):
    """Custom queryset for ChecklistItem with team-scoped access."""

    def for_user(self, user):
        return self.filter(task__bucket__plan__team__memberships__user=user).distinct()


class CommentQuerySet(models.QuerySet):
    """Custom queryset for Comment with team-scoped access."""

    def for_user(self, user):
        return self.filter(task__bucket__plan__team__memberships__user=user).distinct()
