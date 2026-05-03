import pytest

from apps.tasks.api.serializers import CommentSerializer, TaskSerializer


@pytest.mark.django_db
class TestTaskSerializerReadOnlyFields:
    """Server-stamped fields (created_by, completed_at) cannot be set by clients."""

    def test_created_by_is_read_only(self):
        assert TaskSerializer().fields["created_by"].read_only

    def test_completed_at_is_read_only(self):
        """Stamped by the pre_save signal when progress hits 100%."""
        assert TaskSerializer().fields["completed_at"].read_only

    def test_assignees_is_read_only(self):
        """Writes go through Assignment endpoints, not the Task serializer."""
        assert TaskSerializer().fields["assignees"].read_only

    def test_is_overdue_present_and_read_only(self):
        field = TaskSerializer().fields["is_overdue"]
        assert field.read_only
        assert isinstance(field.read_only, bool)


@pytest.mark.django_db
class TestCommentSerializerReadOnlyFields:
    def test_created_by_is_read_only(self):
        assert CommentSerializer().fields["created_by"].read_only
