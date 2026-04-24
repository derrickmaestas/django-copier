import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings

from apps.attachments.tests.factories import AttachmentFactory


@pytest.mark.django_db
class TestAttachmentStr:
    def test_str(self):
        attachment = AttachmentFactory(filename="report.pdf")
        assert str(attachment) == "report.pdf"


@pytest.mark.django_db
class TestAttachmentSizeMb:
    def test_converts_bytes_to_mb(self):
        attachment = AttachmentFactory(size_bytes=5 * 1024 * 1024)
        assert attachment.size_mb == 5.0

    def test_rounds_to_two_decimals(self):
        attachment = AttachmentFactory(size_bytes=1_500_000)
        assert attachment.size_mb == 1.43


@pytest.mark.django_db
class TestAttachmentCleanSizeLimit:
    @override_settings(PLANLY_MAX_ATTACHMENT_SIZE_MB=1)
    def test_rejects_oversized_file(self):
        attachment = AttachmentFactory.build(size_bytes=2 * 1024 * 1024)
        with pytest.raises(ValidationError) as exc:
            attachment.clean()
        assert "exceeds" in str(exc.value)

    @override_settings(PLANLY_MAX_ATTACHMENT_SIZE_MB=5)
    def test_accepts_file_at_limit(self):
        attachment = AttachmentFactory.build(size_bytes=5 * 1024 * 1024)
        attachment.clean()  # should not raise
