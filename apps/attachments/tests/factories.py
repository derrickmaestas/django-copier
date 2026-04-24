import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.attachments.models import Attachment
from apps.tasks.tests.factories import TaskFactory


class AttachmentFactory(DjangoModelFactory):
    class Meta:
        model = Attachment

    task = factory.SubFactory(TaskFactory)
    uploaded_by = factory.SubFactory(UserFactory)
    filename = factory.Sequence(lambda n: f"file_{n}.txt")
    size_bytes = 1024
    content_type = "text/plain"
    file = factory.LazyAttribute(
        lambda obj: SimpleUploadedFile(obj.filename, b"test content")
    )
