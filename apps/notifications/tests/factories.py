import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification, NotificationPreference


class NotificationFactory(DjangoModelFactory):
    class Meta:
        model = Notification

    recipient = factory.SubFactory(UserFactory)
    actor = factory.SubFactory(UserFactory)
    verb = Notification.Verb.ASSIGNED
    description = ""


class NotificationPreferenceFactory(DjangoModelFactory):
    class Meta:
        model = NotificationPreference

    user = factory.SubFactory(UserFactory)
