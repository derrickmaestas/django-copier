from django.contrib.contenttypes.models import ContentType
from django.tasks import task as django_task

from apps.tasks.models import Comment, Task

from .models import Notification


@django_task()
def send_assignment_notification(
    task_id: int,
    assignee_id: int,
    actor_id: int | None = None,
) -> None:
    """Create an in-app notification for a newly assigned user.

    No-op when the actor and the assignee are the same user — assigning
    yourself shouldn't notify yourself.
    """
    if actor_id is not None and actor_id == assignee_id:
        return
    task = Task.objects.filter(pk=task_id).first()
    if task is None:
        return
    Notification.objects.create(
        recipient_id=assignee_id,
        actor_id=actor_id,
        verb=Notification.Verb.ASSIGNED,
        target_content_type=ContentType.objects.get_for_model(Task),
        target_object_id=task.pk,
        description=f'assigned you to "{task.title}"',
    )


@django_task()
def send_comment_notification(comment_id: int) -> None:
    """Notify everyone watching a task when a new comment is posted.

    "Watching" means the task's assignees plus its creator. The commenter
    is removed from the recipient set so people don't get notified about
    their own comments.
    """
    comment = (
        Comment.objects
        .filter(pk=comment_id)
        .select_related("task")
        .first()
    )
    if comment is None:
        return

    task = comment.task
    actor_id = comment.created_by_id

    recipient_ids = set(task.assignees.values_list("pk", flat=True))
    if task.created_by_id is not None:
        recipient_ids.add(task.created_by_id)
    recipient_ids.discard(actor_id)
    if not recipient_ids:
        return

    target_ct = ContentType.objects.get_for_model(Task)
    description = f'commented on "{task.title}"'
    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=rid,
                actor_id=actor_id,
                verb=Notification.Verb.COMMENTED,
                target_content_type=target_ct,
                target_object_id=task.pk,
                description=description,
            )
            for rid in recipient_ids
        ]
    )
