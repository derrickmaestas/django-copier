import pytest
from django.urls import reverse

from apps.accounts.tests.factories import MembershipFactory, UserFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.models import ChecklistItem, Comment, Label, Task
from apps.tasks.tests.factories import (
    ChecklistItemFactory,
    LabelFactory,
    TaskFactory,
)


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


@pytest.mark.django_db
class TestLabelCreateView:
    def test_member_can_create_label(self, client):
        user = UserFactory()
        plan = PlanFactory()
        MembershipFactory(team=plan.team, user=user)
        client.force_login(user)

        response = client.post(
            reverse("tasks:label-create", kwargs={"plan_pk": plan.pk}),
            {"name": "Bug", "color": "#FF0000"},
        )

        assert response.status_code == 302
        assert Label.objects.filter(plan=plan, name="Bug").exists()

    def test_non_member_cannot_create_label(self, client):
        user = UserFactory()
        plan = PlanFactory()
        client.force_login(user)
        response = client.get(reverse("tasks:label-create", kwargs={"plan_pk": plan.pk}))
        assert response.status_code == 404


@pytest.mark.django_db
class TestLabelDeleteView:
    def test_non_member_cannot_delete(self, client):
        user = UserFactory()
        label = LabelFactory()
        client.force_login(user)
        response = client.post(reverse("tasks:label-delete", kwargs={"pk": label.pk}))
        assert response.status_code == 404
        assert Label.objects.filter(pk=label.pk).exists()


@pytest.mark.django_db
class TestChecklistItemAdd:
    def test_member_adds_item_with_auto_position(self, client, member_user_and_task):
        user, task = member_user_and_task
        ChecklistItemFactory(task=task, position=2)  # existing item
        client.force_login(user)

        response = client.post(
            reverse("tasks:checklist-item-add", kwargs={"task_pk": task.pk}),
            {"title": "  Buy milk  "},
        )

        item = ChecklistItem.objects.get(task=task, title="Buy milk")
        assert item.position == 3
        assert response.status_code == 302

    def test_non_member_cannot_add(self, client):
        user = UserFactory()
        task = TaskFactory()
        client.force_login(user)
        response = client.post(
            reverse("tasks:checklist-item-add", kwargs={"task_pk": task.pk}),
            {"title": "Sneaky"},
        )
        assert response.status_code == 404
        assert not ChecklistItem.objects.filter(task=task).exists()


@pytest.mark.django_db
class TestChecklistItemToggle:
    def test_toggle_flips_completed(self, client, member_user_and_task):
        user, task = member_user_and_task
        item = ChecklistItemFactory(task=task, is_completed=False)
        client.force_login(user)

        client.post(reverse("tasks:checklist-item-toggle", kwargs={"pk": item.pk}))
        item.refresh_from_db()
        assert item.is_completed is True

        client.post(reverse("tasks:checklist-item-toggle", kwargs={"pk": item.pk}))
        item.refresh_from_db()
        assert item.is_completed is False

    def test_non_member_cannot_toggle(self, client):
        user = UserFactory()
        item = ChecklistItemFactory(is_completed=False)
        client.force_login(user)
        response = client.post(reverse("tasks:checklist-item-toggle", kwargs={"pk": item.pk}))
        assert response.status_code == 404
        item.refresh_from_db()
        assert item.is_completed is False


@pytest.mark.django_db
class TestChecklistItemDelete:
    def test_non_member_cannot_delete(self, client):
        user = UserFactory()
        item = ChecklistItemFactory()
        client.force_login(user)
        response = client.post(reverse("tasks:checklist-item-delete", kwargs={"pk": item.pk}))
        assert response.status_code == 404
        assert ChecklistItem.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
class TestCommentAdd:
    def test_member_adds_comment(self, client, member_user_and_task):
        user, task = member_user_and_task
        client.force_login(user)

        response = client.post(
            reverse("tasks:comment-add", kwargs={"task_pk": task.pk}),
            {"body": "This needs more detail"},
        )

        comment = Comment.objects.get(task=task)
        assert comment.body == "This needs more detail"
        assert comment.created_by == user
        assert response.status_code == 302

    def test_non_member_cannot_comment(self, client):
        user = UserFactory()
        task = TaskFactory()
        client.force_login(user)
        response = client.post(
            reverse("tasks:comment-add", kwargs={"task_pk": task.pk}),
            {"body": "Sneaky comment"},
        )
        assert response.status_code == 404
        assert not Comment.objects.filter(task=task).exists()


@pytest.mark.django_db
class TestTaskFormValidationInView:
    def test_start_after_due_re_renders_with_error(self, client):
        user = UserFactory()
        bucket = BucketFactory()
        MembershipFactory(team=bucket.plan.team, user=user)
        client.force_login(user)

        response = client.post(
            reverse("tasks:task-create", kwargs={"bucket_pk": bucket.pk}),
            {
                "title": "Bad dates",
                "description": "",
                "priority": Task.Priority.MEDIUM,
                "start_date": "2026-05-10",
                "due_date": "2026-05-01",
            },
        )

        assert response.status_code == 200  # re-renders with errors
        assert not Task.objects.filter(title="Bad dates").exists()
