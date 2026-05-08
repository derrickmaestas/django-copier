from rest_framework import viewsets

from apps.example.models import Item

from .serializers import ItemSerializer


class ItemViewSet(viewsets.ModelViewSet):
    """Team-scoped CRUD for Item."""

    serializer_class = ItemSerializer
    # Empty default lets drf-spectacular introspect the model without
    # needing a real request.user. Real queries go through get_queryset().
    queryset = Item.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Item.objects.none()
        return Item.objects.for_user(self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
