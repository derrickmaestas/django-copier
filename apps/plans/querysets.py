from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db import models
from django.db.models import F

from apps.core.querysets import OrderedQuerySet


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

    def search(self, query: str, *, with_headline: bool = False):
        """Full-text search ranked by ts_rank_cd against `search_vector`.

        Uses Postgres' `websearch_to_tsquery`, which accepts the same
        natural-language operators users already know from web search:
        quoted phrases, `OR`, and `-excluded`. Empty/whitespace queries
        return an empty queryset (callers don't have to special-case it).

        `with_headline=True` annotates a `headline` field with the
        matched snippet wrapped in <b>…</b> markers — used by the API,
        skipped by the HTML list view to keep templates simple.
        """
        cleaned = (query or "").strip()
        if not cleaned:
            return self.none()
        ts_query = SearchQuery(cleaned, search_type="websearch", config="english_unaccent")
        # SearchRank("search_vector", ...) re-tokenizes the stored vector
        # as text — silently dropping the A/B weights we worked to build
        # in the GeneratedField. Wrapping the field in F() forces Django
        # to use the existing tsvector directly. Verified against the
        # generated SQL: with F() it emits `ts_rank(search_vector, ...)`,
        # without it emits `ts_rank(to_tsvector(coalesce(text(...), '')), ...)`.
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


class BucketQuerySet(OrderedQuerySet):
    """Custom queryset for Bucket with team-scoped access."""

    def for_user(self, user):
        """Return buckets in plans visible to this user through team membership."""
        return self.filter(plan__team__memberships__user=user).distinct()
