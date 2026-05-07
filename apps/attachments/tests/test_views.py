import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.tests.factories import (
    MembershipFactory,
    TeamFactory,
    UserFactory,
)
from apps.attachments.models import Attachment
from apps.attachments.tests.factories import AttachmentFactory
from apps.plans.tests.factories import BucketFactory, PlanFactory
from apps.tasks.tests.factories import TaskFactory

# A real PDF magic-number prefix — the validator's libmagic sniff
# accepts this; an `MZ`-prefixed payload would be rejected.
PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"0" * 256


def _make_pdf(name="report.pdf"):
    return SimpleUploadedFile(name, PDF_BYTES, content_type="application/pdf")


@pytest.fixture
def member_team(client):
    user = UserFactory()
    user.set_password("pw")
    user.save()
    team = TeamFactory()
    MembershipFactory(team=team, user=user)
    bucket = BucketFactory(plan=PlanFactory(team=team))
    task = TaskFactory(bucket=bucket)
    client.force_login(user)
    return client, user, team, task


@pytest.mark.django_db
class TestAttachmentUpload:
    """POST /attachments/task/<pk>/upload/ creates an Attachment + saves the file."""

    def test_member_can_upload(self, member_team):
        client, user, team, task = member_team

        response = client.post(
            reverse("attachments:attachment-upload", kwargs={"task_pk": task.pk}),
            {"file": _make_pdf()},
        )

        assert response.status_code == 302
        attachment = Attachment.objects.get()
        assert attachment.task == task
        assert attachment.uploaded_by == user
        assert attachment.filename == "report.pdf"
        assert attachment.size_bytes > 0

    def test_htmx_request_returns_attachment_partial(self, member_team):
        client, user, team, task = member_team

        response = client.post(
            reverse("attachments:attachment-upload", kwargs={"task_pk": task.pk}),
            {"file": _make_pdf()},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        # Partial — no <html> shell, just the <li>.
        assert b"<html" not in response.content
        assert b"report.pdf" in response.content

    def test_validator_failure_rejects_with_422_on_htmx(self, member_team):
        """A renamed-executable upload triggers libmagic and gets refused."""
        client, user, team, task = member_team
        bad = SimpleUploadedFile(
            "payload.pdf", b"MZ\x90\x00" + b"\x00" * 64, content_type="application/pdf"
        )

        response = client.post(
            reverse("attachments:attachment-upload", kwargs={"task_pk": task.pk}),
            {"file": bad},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 422
        assert b"not allowed" in response.content
        assert Attachment.objects.count() == 0

    def test_non_member_cannot_upload(self, member_team):
        """A task on someone else's team is not visible — 404, not 403."""
        client, _, _, _ = member_team
        other_task = TaskFactory(bucket=BucketFactory(plan=PlanFactory(team=TeamFactory())))

        response = client.post(
            reverse("attachments:attachment-upload", kwargs={"task_pk": other_task.pk}),
            {"file": _make_pdf()},
        )

        assert response.status_code == 404
        assert Attachment.objects.count() == 0

    def test_get_not_allowed(self, member_team):
        client, _, _, task = member_team
        response = client.get(
            reverse("attachments:attachment-upload", kwargs={"task_pk": task.pk})
        )
        assert response.status_code == 405


@pytest.mark.django_db
class TestAttachmentDelete:
    """POST /attachments/<pk>/delete/ removes the row and the file."""

    def test_member_can_delete(self, member_team):
        client, user, team, task = member_team
        attachment = AttachmentFactory(task=task, uploaded_by=user)

        response = client.post(
            reverse("attachments:attachment-delete", kwargs={"pk": attachment.pk})
        )

        assert response.status_code == 302
        assert not Attachment.objects.filter(pk=attachment.pk).exists()

    def test_htmx_returns_empty_200(self, member_team):
        """HTMX outerHTML swap on empty body removes the row from the DOM."""
        client, user, team, task = member_team
        attachment = AttachmentFactory(task=task, uploaded_by=user)

        response = client.post(
            reverse("attachments:attachment-delete", kwargs={"pk": attachment.pk}),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert response.content == b""
        assert not Attachment.objects.filter(pk=attachment.pk).exists()

    def test_non_member_cannot_delete(self, member_team):
        client, _, _, _ = member_team
        other_task = TaskFactory(bucket=BucketFactory(plan=PlanFactory(team=TeamFactory())))
        attachment = AttachmentFactory(task=other_task)

        response = client.post(
            reverse("attachments:attachment-delete", kwargs={"pk": attachment.pk})
        )

        assert response.status_code == 404
        # Row still exists — non-member can't even see it to delete it.
        assert Attachment.objects.filter(pk=attachment.pk).exists()
