import pytest
from django.urls import reverse

from apps.accounts.tests.factories import MembershipFactory, UserFactory
from apps.plans.tests.factories import BucketFactory
from apps.tasks.models import Task
from apps.tasks.tests.factories import TaskFactory


@pytest.fixture
def member_user_and_task(db):
    user = UserFactory()
    task = TaskFactory()
    MembershipFactory(team=task.bucket.plan.team, user=user)
    return user, task


@pytest.mark.django_db
class TestTaskDetailView:
    def test_team_member_can_view(self, client, member_user_and_task):
        user, task = member_user_and_task
        client.force_login(user)
        response = client.get(reverse("tasks:task-detail", kwargs={"pk": task.pk}))
        assert response.status_code == 200

    def test_non_member_gets_404(self, client):
        user = UserFactory()
        task = TaskFactory()
        client.force_login(user)
        response = client.get(reverse("tasks:task-detail", kwargs={"pk": task.pk}))
        assert response.status_code == 404


@pytest.mark.django_db
class TestTaskCreateView:
    def test_member_creates_task_in_bucket(self, client):
        user = UserFactory()
        bucket = BucketFactory()
        MembershipFactory(team=bucket.plan.team, user=user)
        client.force_login(user)

        response = client.post(
            reverse("tasks:task-create", kwargs={"bucket_pk": bucket.pk}),
            {
                "title": "New task",
                "description": "",
                "priority": Task.Priority.MEDIUM,
                "due_date": "",
                "start_date": "",
            },
        )

        task = Task.objects.get(title="New task")
        assert task.bucket == bucket
        assert task.created_by == user
        assert response.status_code == 302

    def test_non_member_cannot_create_in_bucket(self, client):
        user = UserFactory()
        bucket = BucketFactory()
        client.force_login(user)
        response = client.get(reverse("tasks:task-create", kwargs={"bucket_pk": bucket.pk}))
        assert response.status_code == 404


@pytest.mark.django_db
class TestTaskMarkComplete:
    def test_member_marks_complete(self, client, member_user_and_task):
        user, task = member_user_and_task
        client.force_login(user)
        response = client.post(reverse("tasks:task-complete", kwargs={"pk": task.pk}))
        task.refresh_from_db()
        assert task.progress == Task.Progress.COMPLETED
        assert task.completed_at is not None
        assert response.status_code == 302

    def test_non_member_gets_404(self, client):
        user = UserFactory()
        task = TaskFactory()
        client.force_login(user)
        response = client.post(reverse("tasks:task-complete", kwargs={"pk": task.pk}))
        assert response.status_code == 404
        task.refresh_from_db()
        assert task.progress != Task.Progress.COMPLETED

    def test_get_not_allowed(self, client, member_user_and_task):
        user, task = member_user_and_task
        client.force_login(user)
        response = client.get(reverse("tasks:task-complete", kwargs={"pk": task.pk}))
        assert response.status_code == 405


@pytest.mark.django_db
class TestTaskDeleteView:
    def test_non_member_cannot_delete(self, client):
        user = UserFactory()
        task = TaskFactory()
        client.force_login(user)
        response = client.post(reverse("tasks:task-delete", kwargs={"pk": task.pk}))
        assert response.status_code == 404
        assert Task.objects.filter(pk=task.pk).exists()
