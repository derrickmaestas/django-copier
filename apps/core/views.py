from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.plans.models import Plan
from apps.tasks.models import Task

ALLOWED_TYPES = {"plan", "task"}


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
