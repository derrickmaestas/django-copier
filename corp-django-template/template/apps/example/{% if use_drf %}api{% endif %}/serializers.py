from rest_framework import serializers

from apps.example.models import Item


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "name", "description", "team", "created_by", "created_at", "modified_at"]
        read_only_fields = ["id", "created_by", "created_at", "modified_at"]
