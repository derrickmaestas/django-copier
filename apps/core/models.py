from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base that adds created_at and modified_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Ensure modified_at is always written, even when save() is called
        # with update_fields. Without this, save(update_fields=["title"])
        # would skip the auto_now field entirely.
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "modified_at"}
        super().save(*args, **kwargs)


class OrderedModel(models.Model):
    """Abstract base that adds a position field for drag-and-drop ordering."""

    position = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["position"]
