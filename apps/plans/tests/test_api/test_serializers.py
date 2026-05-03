import pytest

from apps.plans.api.serializers import BucketSerializer, PlanSerializer


@pytest.mark.django_db
class TestPlanSerializerReadOnlyFields:
    """Server-stamped fields must be marked read-only on the serializer."""

    def test_created_by_is_read_only(self):
        assert PlanSerializer().fields["created_by"].read_only

    def test_id_and_timestamps_are_read_only(self):
        for name in ["id", "created_at", "modified_at"]:
            assert PlanSerializer().fields[name].read_only, f"{name} should be read-only"

    def test_writable_fields_present(self):
        """The serializer must expose the right write fields for create/update."""
        writable = {
            name for name, field in PlanSerializer().fields.items() if not field.read_only
        }
        assert {"title", "team", "visibility"} <= writable


@pytest.mark.django_db
class TestBucketSerializerReadOnlyFields:
    """Position is server-assigned via the dedicated reorder action."""

    def test_position_is_read_only(self):
        assert BucketSerializer().fields["position"].read_only

    def test_id_and_timestamps_are_read_only(self):
        for name in ["id", "created_at", "modified_at"]:
            assert BucketSerializer().fields[name].read_only
