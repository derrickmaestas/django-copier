from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.tasks.models import Comment, Task

from .filters import TaskFilter
from .serializers import CommentSerializer, TaskSerializer


class TaskViewSet(viewsets.ModelViewSet):
    """CRUD for Tasks, scoped to the user's team memberships.

    Filtering: `?bucket=`, `?plan=`, `?priority=`, `?progress=`,
    `?assignee=` (user employee_id). Search: `?search=` matches title
    and description. Ordering: `?ordering=-due_date`, `?ordering=priority`.

    `select_related("bucket")` and `prefetch_related("assignees")`
    keep the list endpoint to a stable query count regardless of how
    many tasks come back — the kanban view depends on this not
    blowing up under N+1.
    """

    queryset = Task.objects.none()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = TaskFilter
    search_fields = ["title", "description"]
    ordering_fields = ["due_date", "priority", "created_at", "progress"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Task.objects.for_user(self.request.user)
            .select_related("bucket", "created_by")
            .prefetch_related("assignees")
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CommentViewSet(viewsets.ModelViewSet):
    """CRUD for Comments. List with `?task=<id>` to scope to a task.

    `created_by` is stamped from the request and the target Task is
    re-resolved through `for_user(...)` so a non-member can't comment
    on a task they couldn't otherwise see.
    """

    queryset = Comment.objects.none()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["task"]
    ordering_fields = ["created_at"]
    ordering = ["created_at"]

    def get_queryset(self):
        return Comment.objects.for_user(self.request.user).select_related(
            "task", "created_by"
        )

    def perform_create(self, serializer):
        # Re-fetch the task through for_user() so we 404 if the requester
        # isn't a team member, even if the task pk is technically valid.
        task = get_object_or_404(
            Task.objects.for_user(self.request.user),
            pk=serializer.validated_data["task"].pk,
        )
        serializer.save(created_by=self.request.user, task=task)
