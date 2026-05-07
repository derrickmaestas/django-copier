from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.plans.models import Plan
from apps.tasks.models import Task

ALLOWED_TYPES = {"plan", "task"}


@require_GET
def health(request):
    """Liveness + readiness probe.

    Returns 200 with `{"status": "ok"}` when the process is reachable
    AND the database is. Returns 503 with `{"status": "db_unreachable"}`
    when the database connection can't be established.

    Authentication is intentionally NOT required: load balancers and
    container orchestrators probe this endpoint without credentials.
    The endpoint reveals only liveness — no app version, no user info,
    no environment string — so leaving it public is safe.
    """
    try:
        connection.ensure_connection()
    except DatabaseError:
        return JsonResponse({"status": "db_unreachable"}, status=503)
    return JsonResponse({"status": "ok"})


@login_required
def search(request):
    """Unified full-text search across Plans and Tasks.

    Query parameters:
      `q`    — the search string. Empty/missing → empty result lists.
      `type` — `plan` or `task` to filter to a single resource. Any other
               value (including absent) returns mixed results.

    HTMX requests get just the results pane (the tabs swap inline);
    regular requests get the full page including the search header.
    """
    query = (request.GET.get("q") or "").strip()
    type_filter = request.GET.get("type")
    if type_filter not in ALLOWED_TYPES:
        type_filter = None

    plans = Plan.objects.none()
    tasks = Task.objects.none()
    if query:
        if type_filter is None or type_filter == "plan":
            plans = Plan.objects.for_user(request.user).search(query)[:25]
        if type_filter is None or type_filter == "task":
            tasks = (
                Task.objects.for_user(request.user)
                .search(query)
                .select_related("bucket", "bucket__plan")[:25]
            )

    context = {
        "query": query,
        "type_filter": type_filter,
        "plans": plans,
        "tasks": tasks,
    }
    template = (
        "core/search.html#results"
        if request.headers.get("HX-Request") == "true"
        else "core/search.html"
    )
    return render(request, template, context)
