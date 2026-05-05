import pytest

from apps.core.api.serializers import SearchHitSerializer


@pytest.mark.django_db
class TestSearchHitSerializer:
    """SearchHitSerializer flattens any indexable resource into a uniform shape."""

    def test_serializes_a_plan_hit(self):
        hit = {
            "type": "plan",
            "id": 1,
            "title": "Q3 Roadmap",
            "url": "/plans/1/",
            "rank": 0.123,
            "headline": "Q3 <b>roadmap</b> for the team",
        }

        data = SearchHitSerializer(hit).data

        assert data["type"] == "plan"
        assert data["headline"] == "Q3 <b>roadmap</b> for the team"

    def test_blank_headline_is_allowed(self):
        """Some hits (e.g., title-only matches with empty descriptions) have no snippet."""
        hit = {
            "type": "task",
            "id": 5,
            "title": "Untitled",
            "url": "/tasks/5/",
            "rank": 0.1,
            "headline": "",
        }

        data = SearchHitSerializer(hit).data

        assert data["headline"] == ""
