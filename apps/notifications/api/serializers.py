from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Notification resource for the API.

    The GenericForeignKey `target` is exposed as a flat
    `{type, id}` pair rather than a fully-serialized nested object —
    clients can fetch the target detail by visiting its own endpoint.
    Inlining a polymorphic object is messy in OpenAPI; keeping it as
    a reference keeps the schema clean.
    """

    target_type = serializers.SerializerMethodField()
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "actor",
            "verb",
            "description",
            "target_type",
            "target_object_id",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_target_type(self, obj) -> str | None:
        ct = obj.target_content_type
        return None if ct is None else f"{ct.app_label}.{ct.model}"
