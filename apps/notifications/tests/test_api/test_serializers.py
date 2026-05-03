import pytest
from django.contrib.contenttypes.models import ContentType

from apps.notifications.api.serializers import NotificationSerializer
from apps.notifications.tests.factories import NotificationFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.models import Task
from apps.tasks.tests.factories import TaskFactory


@pytest.mark.django_db
class TestNotificationSerializerReadOnly:
    """Notifications are server-emitted; the entire serializer is read-only."""

    def test_all_fields_read_only(self):
        for name, field in NotificationSerializer().fields.items():
            assert field.read_only, f"{name} should be read-only"


@pytest.mark.django_db
class TestNotificationSerializerTargetType:
    """`target_type` flattens the GenericForeignKey into 'app.model'."""

    def test_renders_target_type_as_app_model_string(self):
        task = TaskFactory(bucket=BucketFactory(plan=PlanFactory()))
        notif = NotificationFactory(
            target_content_type=ContentType.objects.get_for_model(Task),
            target_object_id=task.pk,
        )

        data = NotificationSerializer(notif).data

        assert data["target_type"] == "tasks.task"
        assert data["target_object_id"] == task.pk

    def test_target_type_is_none_when_no_target(self):
        notif = NotificationFactory(
            target_content_type=None, target_object_id=None
        )

        data = NotificationSerializer(notif).data

        assert data["target_type"] is None
