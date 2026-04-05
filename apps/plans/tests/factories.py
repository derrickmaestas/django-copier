import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import TeamFactory
from apps.plans.models import Bucket, Plan


class PlanFactory(DjangoModelFactory):
    class Meta:
        model = Plan

    title = factory.Sequence(lambda n: f"Plan {n}")
    description = ""
    team = factory.SubFactory(TeamFactory)
    owner = factory.LazyAttribute(lambda obj: obj.team.owner)
    created_by = factory.LazyAttribute(lambda obj: obj.owner)
    visibility = Plan.Visibility.PRIVATE


class BucketFactory(DjangoModelFactory):
    class Meta:
        model = Bucket

    plan = factory.SubFactory(PlanFactory)
    title = factory.Sequence(lambda n: f"Bucket {n}")
    position = factory.Sequence(lambda n: n)
