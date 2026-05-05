from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db import models
from django.db.models import F
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

    def search(self, query: str, *, with_headline: bool = False):
        """Full-text search ranked by ts_rank_cd against `search_vector`.

        Hits include matches in the task's own title/description AND
        in any of its comments (the trigger keeps the vector in sync).
        Uses Postgres' websearch_to_tsquery for natural input — quoted
        phrases, OR, and -excluded all work. Empty query → empty qs.

        `with_headline=True` annotates a `headline` snippet built from
        `description` with <b>match</b> markers, used by the API.
        """
        cleaned = (query or "").strip()
        if not cleaned:
            return self.none()
        ts_query = SearchQuery(cleaned, search_type="websearch", config="english_unaccent")
        # F("search_vector") (not "search_vector") so SearchRank consumes
        # the stored tsvector directly — see the longer comment in
        # apps/plans/querysets.py for the gotcha this avoids.
        qs = self.filter(search_vector=ts_query).annotate(
            rank=SearchRank(F("search_vector"), ts_query),
        )
        if with_headline:
            qs = qs.annotate(
                headline=SearchHeadline(
                    "description",
                    ts_query,
                    config="english_unaccent",
                    start_sel="<b>",
                    stop_sel="</b>",
                )
            )
        return qs.order_by("-rank", "-created_at")


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
