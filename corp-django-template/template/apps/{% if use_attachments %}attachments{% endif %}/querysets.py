from django.db import models


class AttachmentQuerySet(models.QuerySet):
    """Common scoping helpers for Attachment.

    `for_target(obj)` filters to attachments on a specific object.
    Cross-app team-scoping (`for_user(user)`) is project-specific —
    add it in your domain app once you know how Attachment relates
    to your team membership model.
    """

    def for_target(self, obj):
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(type(obj))
        return self.filter(target_content_type=ct, target_object_id=obj.pk)
