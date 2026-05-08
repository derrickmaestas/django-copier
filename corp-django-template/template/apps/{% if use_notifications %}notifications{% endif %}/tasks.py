"""Background tasks for the notifications app.

Enqueued from signal handlers in the source app (e.g.
apps/example/signals.py for the placeholder Item).

Naming: tasks here are named for the *thing* being notified about,
not the model it lives on. Replace `send_item_notification` when you
swap apps/example for your domain models.
"""

from django.contrib.contenttypes.models import ContentType
from django.tasks import task as django_task

from apps.example.models import Item

from .models import Notification


@django_task()
def send_item_notification(item_id: int) -> None:
    """Notify all team members when a new Item is created.

    No-op when the item is missing (e.g. deleted between enqueue and
    dispatch). The author is excluded from the recipient set so they
    don't get notified about their own creation.
    """
    item = Item.objects.filter(pk=item_id).select_related("team").first()
    if item is None:
        return

    actor_id = item.created_by_id
    recipient_ids = set(
        item.team.memberships.exclude(user_id=actor_id).values_list("user_id", flat=True)
    )
    if not recipient_ids:
        return

    target_ct = ContentType.objects.get_for_model(Item)
    description = f'created "{item.name}"'
    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=rid,
                actor_id=actor_id,
                verb=Notification.Verb.CREATED,
                target_content_type=target_ct,
                target_object_id=item.pk,
                description=description,
            )
            for rid in recipient_ids
        ]
    )
