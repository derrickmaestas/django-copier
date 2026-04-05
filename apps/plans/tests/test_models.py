from django.test import TestCase

from apps.plans.tests.factories import BucketFactory, PlanFactory


class TestPlan(TestCase):
    def test_str(self):
        plan = PlanFactory(title="Sprint 42")
        assert str(plan) == "Sprint 42"


class TestBucket(TestCase):
    def test_str(self):
        bucket = BucketFactory(title="In Progress")
        assert str(bucket) == "In Progress"
