import pytest

from apps.example.tests.factories import ItemFactory


@pytest.mark.django_db
class TestItem:
    def test_str_returns_name(self):
        item = ItemFactory(name="Hello")
        assert str(item) == "Hello"
