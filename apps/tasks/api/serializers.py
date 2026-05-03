from rest_framework import serializers

from apps.tasks.models import Comment, Task


class TaskSerializer(serializers.ModelSerializer):
    """Task resource for the API.

    `assignees` is exposed as a list of employee_ids (the User PK).
    Writes through this field create/delete Assignment rows
    automatically — DRF's ModelSerializer handles the M2M-through case
    when the through model has no extra required fields beyond the
    two FKs.
    """

    assignees = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
    )
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "bucket",
            "title",
            "description",
            "priority",
            "progress",
            "due_date",
            "completed_at",
            "start_date",
            "created_by",
            "assignees",
            "is_overdue",
            "created_at",
            "modified_at",
        ]
        read_only_fields = [
            "id",
            "completed_at",
            "created_by",
            "is_overdue",
            "created_at",
            "modified_at",
        ]


class CommentSerializer(serializers.ModelSerializer):
    """Comment on a task. `created_by` is server-stamped from the request."""

    class Meta:
        model = Comment
        fields = ["id", "task", "body", "created_by", "created_at", "modified_at"]
        read_only_fields = ["id", "created_by", "created_at", "modified_at"]
