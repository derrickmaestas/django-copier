from django.db import models
from django.db.models import Max


class OrderedQuerySet(models.QuerySet):
    """QuerySet base for OrderedModel subclasses.

    Adds a `next_position(**filters)` helper that returns the next
    available position within a scope.
    """

    def next_position(self, **filters) -> int:
        last = self.filter(**filters).aggregate(Max("position"))["position__max"]
        return (last or 0) + 1
