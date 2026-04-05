from django.db import models
from django.test import TestCase
from django.utils import timezone

from apps.core.models import OrderedModel, TimeStampedModel


# Concrete models for testing abstract bases — these get real tables
# via pytest-django's --no-migrations flag (creates tables from model defs).
class ConcreteTimeStamped(TimeStampedModel):
    title = models.CharField(max_length=100)

    class Meta:
        app_label = "core"


class ConcreteOrdered(OrderedModel):
    title = models.CharField(max_length=100)

    class Meta(OrderedModel.Meta):
        app_label = "core"


class ConcreteTimeStampedOrdered(TimeStampedModel, OrderedModel):
    """Tests that both abstract models can be composed together."""

    title = models.CharField(max_length=100)

    class Meta(OrderedModel.Meta):
        app_label = "core"


class TestTimeStampedModel(TestCase):
    def test_created_at_set_on_create(self):
        obj = ConcreteTimeStamped.objects.create(title="test")
        assert obj.created_at is not None
        assert obj.created_at <= timezone.now()

    def test_modified_at_set_on_create(self):
        obj = ConcreteTimeStamped.objects.create(title="test")
        assert obj.modified_at is not None

    def test_modified_at_changes_on_save(self):
        obj = ConcreteTimeStamped.objects.create(title="test")
        original_updated = obj.modified_at
        obj.title = "changed"
        obj.save()
        obj.refresh_from_db()
        assert obj.modified_at > original_updated

    def test_created_at_unchanged_on_save(self):
        obj = ConcreteTimeStamped.objects.create(title="test")
        original_created = obj.created_at
        obj.title = "changed"
        obj.save()
        obj.refresh_from_db()
        assert obj.created_at == original_created

    def test_modified_at_changes_with_update_fields(self):
        obj = ConcreteTimeStamped.objects.create(title="test")
        original_updated = obj.modified_at
        obj.title = "changed"
        obj.save(update_fields=["title"])
        obj.refresh_from_db()
        assert obj.modified_at > original_updated

    def test_is_abstract(self):
        assert TimeStampedModel._meta.abstract is True


class TestOrderedModel(TestCase):
    def test_default_position_is_zero(self):
        obj = ConcreteOrdered.objects.create(title="first")
        assert obj.position == 0

    def test_position_can_be_set(self):
        obj = ConcreteOrdered.objects.create(title="second", position=5)
        assert obj.position == 5

    def test_ordering_by_position(self):
        ConcreteOrdered.objects.create(title="third", position=3)
        ConcreteOrdered.objects.create(title="first", position=1)
        ConcreteOrdered.objects.create(title="second", position=2)
        titles = list(ConcreteOrdered.objects.values_list("title", flat=True))
        assert titles == ["first", "second", "third"]

    def test_position_is_indexed(self):
        field = ConcreteOrdered._meta.get_field("position")
        assert field.db_index is True

    def test_is_abstract(self):
        assert OrderedModel._meta.abstract is True


class TestComposedModels(TestCase):
    def test_has_all_fields(self):
        obj = ConcreteTimeStampedOrdered.objects.create(title="test", position=1)
        assert obj.created_at is not None
        assert obj.modified_at is not None
        assert obj.position == 1
