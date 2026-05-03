from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notifications.models import Notification

from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list of the current user's notifications.

    Notifications are server-emitted (signals + django.tasks); clients
    don't create them. The only mutation we expose is marking them
    read — a custom action keeps the URL semantic
    (POST `…/{id}/mark_read/`) without overloading PATCH.

    `mark_all_read` is a collection-level action (POST
    `/api/v1/notifications/mark_all_read/`) that bulk-marks every
    unread notification — preferred over N round-trips for the
    "clear notifications" UX pattern.
    """

    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["verb"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # `for_user(...)` filters to recipient=user — a recipient can only
        # ever see their own notifications regardless of team membership.
        return Notification.objects.for_user(self.request.user).select_related(
            "actor", "target_content_type"
        )

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_read()
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        updated = self.get_queryset().mark_all_read()
        return Response({"updated": updated})
