import pytest

from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory
from apps.example.models import Item
from apps.example.tests.factories import ItemFactory


@pytest.mark.django_db
class TestForUser:
    def test_returns_items_in_user_teams(self):
        team = TeamFactory()
        user = UserFactory()
        MembershipFactory(team=team, user=user)
        in_team = ItemFactory(team=team)
        ItemFactory()  # different team

        result = list(Item.objects.for_user(user))

        assert in_team in result
        assert len(result) == 1

    def test_returns_empty_for_user_with_no_team(self):
        ItemFactory()
        loner = UserFactory()

        assert list(Item.objects.for_user(loner)) == []
