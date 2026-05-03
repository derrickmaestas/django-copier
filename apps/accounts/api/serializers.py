from rest_framework import serializers

from apps.accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    """Read-only projection of a user for API responses.

    `employee_id` is the primary key and the username — exposing it
    lets clients link comments / assignments back to a known user
    without leaking email or password fields.
    """

    class Meta:
        model = User
        fields = ["employee_id", "display_name", "email", "is_manager"]
        read_only_fields = fields
