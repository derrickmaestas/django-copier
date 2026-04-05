import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.models import Assignment, ChecklistItem, Comment, Label, Task


class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    bucket = factory.SubFactory(BucketFactory)
    title = factory.Sequence(lambda n: f"Task {n}")
    description = ""
    priority = Task.Priority.MEDIUM
    progress = Task.Progress.NOT_STARTED
    created_by = factory.SubFactory(UserFactory)


class AssignmentFactory(DjangoModelFactory):
    class Meta:
        model = Assignment

    task = factory.SubFactory(TaskFactory)
    user = factory.SubFactory(UserFactory)


class ChecklistItemFactory(DjangoModelFactory):
    class Meta:
        model = ChecklistItem

    task = factory.SubFactory(TaskFactory)
    title = factory.Sequence(lambda n: f"Checklist item {n}")
    position = factory.Sequence(lambda n: n)
    is_completed = False


class LabelFactory(DjangoModelFactory):
    class Meta:
        model = Label

    plan = factory.SubFactory(PlanFactory)
    name = factory.Sequence(lambda n: f"Label {n}")
    color = "#6B7280"


class CommentFactory(DjangoModelFactory):
    class Meta:
        model = Comment

    task = factory.SubFactory(TaskFactory)
    created_by = factory.SubFactory(UserFactory)
    body = factory.Sequence(lambda n: f"Comment body {n}")
