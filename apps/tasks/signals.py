from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.notifications.tasks import send_comment_notification

from .models import Comment, Task


@receiver(post_save, sender=Comment)
def comment_post_save(sender, instance, created, **kwargs):
    """Fan a new comment out to everyone watching the task."""
    if not created:
        return
    send_comment_notification.enqueue(instance.pk)


@receiver(pre_save, sender=Task)
def task_pre_save_set_completed_at(sender, instance, **kwargs):
    """Stamp ``completed_at`` whenever a task transitions to 100% progress.

    ``Task.mark_complete()`` already does this, but anything that bypasses
    that helper — direct ``task.save()``, the admin, the API, raw fixtures —
    would leave ``completed_at`` stale. Treat this signal as a safety net
    for the invariant rather than the primary code path.
    """
    if instance.progress != Task.Progress.COMPLETED:
        return

    if instance.pk is None:
        if instance.completed_at is None:
            instance.completed_at = timezone.now()
        return

    previous = (
        Task.objects.filter(pk=instance.pk)
        .only("progress", "completed_at")
        .first()
    )
    if previous is None:
        return
    transitioning = previous.progress != Task.Progress.COMPLETED
    if transitioning and instance.completed_at is None:
        instance.completed_at = timezone.now()
