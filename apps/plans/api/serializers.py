from rest_framework import serializers

from apps.plans.models import Bucket, Plan


class PlanSerializer(serializers.ModelSerializer):
    """Plan resource for the API.

    `created_by` and `owner` are write-once / server-set: clients can
    create a plan but the server stamps `created_by` from the request
    user. They're read-only here so we don't trust client-supplied
    values for "who made this".
    """

    class Meta:
        model = Plan
        fields = [
            "id",
            "title",
            "description",
            "team",
            "owner",
            "created_by",
            "visibility",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "modified_at"]


class BucketSerializer(serializers.ModelSerializer):
    """Bucket resource — a column on a plan.

    `position` is read-only here because the dedicated `reorder` action
    on the ViewSet is the canonical way to change order; allowing
    arbitrary writes makes it easy to leave gaps or duplicates.
    """

    class Meta:
        model = Bucket
        fields = ["id", "plan", "title", "position", "created_at", "modified_at"]
        read_only_fields = ["id", "position", "created_at", "modified_at"]
