from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.plans.models import Plan
from apps.tasks.models import Task

from .serializers import SearchHitSerializer

ALLOWED_TYPES = {"plan", "task"}
RESULT_LIMIT = 25


class SearchView(APIView):
    """GET /api/v1/search/?q=<query>&type=<plan|task>

    Mixed-resource search. Each hit carries its `type`, `id`, `url`,
    `rank` (ts_rank_cd), and `headline` (matched snippet). When `type`
    is omitted, both kinds are returned and merged by rank — so the
    most relevant hit of either kind floats to the top.

    Capped at 25 results per resource. Pagination is intentionally
    skipped — search is for the "I know what I want, find it now"
    flow, not for browsing all matches.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = SearchHitSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(name="q", type=str, required=True, location="query"),
            OpenApiParameter(
                name="type", type=str, required=False, location="query",
                enum=sorted(ALLOWED_TYPES),
            ),
        ],
        responses=SearchHitSerializer(many=True),
    )
    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        type_filter = request.query_params.get("type")
        if type_filter not in ALLOWED_TYPES:
            type_filter = None

        if not query:
            return Response([])

        hits: list[dict] = []
        if type_filter is None or type_filter == "plan":
            for plan in (
                Plan.objects.for_user(request.user)
                .search(query, with_headline=True)[:RESULT_LIMIT]
            ):
                hits.append({
                    "type": "plan",
                    "id": plan.pk,
                    "title": plan.title,
                    "url": f"/plans/{plan.pk}/",
                    "rank": float(plan.rank),
                    "headline": plan.headline,
                })
        if type_filter is None or type_filter == "task":
            for task in (
                Task.objects.for_user(request.user)
                .search(query, with_headline=True)
                .select_related("bucket")[:RESULT_LIMIT]
            ):
                hits.append({
                    "type": "task",
                    "id": task.pk,
                    "title": task.title,
                    "url": f"/tasks/{task.pk}/",
                    "rank": float(task.rank),
                    "headline": task.headline,
                })

        # When both types are returned, merge by rank so the strongest
        # match wins regardless of kind. Stable sort preserves the
        # underlying `-created_at` tiebreak we set in the queryset.
        hits.sort(key=lambda hit: hit["rank"], reverse=True)
        return Response(SearchHitSerializer(hits, many=True).data)
