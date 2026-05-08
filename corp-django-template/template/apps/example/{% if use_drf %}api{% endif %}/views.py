from rest_framework import viewsets

from apps.example.models import Item

from .serializers import ItemSerializer


class ItemViewSet(viewsets.ModelViewSet):
    """Team-scoped CRUD for Item."""

    serializer_class = ItemSerializer

    def get_queryset(self):
        return Item.objects.for_user(self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
