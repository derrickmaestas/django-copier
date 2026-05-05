import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.attachments.validators import (
    run_all,
    validate_content_type,
    validate_extension,
    validate_filename,
    validate_size,
)


def _make_file(name: str, content: bytes, content_type: str = "application/pdf"):
    """Build a Django UploadedFile with the bytes and metadata a real upload would carry."""
    return SimpleUploadedFile(name, content, content_type=content_type)


class TestValidateFilename:
    """Filename safety: no path escape, no double extensions, no leading dots."""

    def test_accepts_simple_filename(self):
        validate_filename("report.pdf")

    def test_rejects_path_separator(self):
        with pytest.raises(ValidationError, match="illegal characters"):
            validate_filename("../etc/passwd")

    def test_rejects_backslash_separator(self):
        with pytest.raises(ValidationError, match="illegal characters"):
            validate_filename("docs\\evil.pdf")

    def test_rejects_null_byte(self):
        with pytest.raises(ValidationError, match="illegal characters"):
            validate_filename("report.pdf\x00.exe")

    def test_rejects_leading_dot(self):
        with pytest.raises(ValidationError, match="not start with a dot"):
            validate_filename(".bashrc")

    def test_rejects_double_extension(self):
        """invoice.pdf.exe — the classic disguise trick."""
        with pytest.raises(ValidationError, match="exactly one extension"):
            validate_filename("invoice.pdf.exe")

    def test_rejects_empty_filename(self):
        with pytest.raises(ValidationError, match="must have a filename"):
            validate_filename("")


class TestValidateSize:
    """Size cap honors PLANLY_MAX_ATTACHMENT_SIZE_MB."""

    @override_settings(PLANLY_MAX_ATTACHMENT_SIZE_MB=1)
    def test_under_limit_passes(self):
        upload = _make_file("ok.pdf", b"x" * 500_000)  # 0.5 MB
        validate_size(upload)

    @override_settings(PLANLY_MAX_ATTACHMENT_SIZE_MB=1)
    def test_over_limit_rejected(self):
        upload = _make_file("big.pdf", b"x" * 2_000_000)  # 2 MB
        with pytest.raises(ValidationError, match="exceeds the 1 MB limit"):
            validate_size(upload)


class TestValidateExtension:
    """Extension allowlist."""

    def test_allows_pdf(self):
        validate_extension("doc.pdf")

    def test_allows_uppercase(self):
        validate_extension("PHOTO.JPG")

    def test_rejects_executable(self):
        with pytest.raises(ValidationError, match="not allowed"):
            validate_extension("payload.exe")

    def test_rejects_no_extension(self):
        with pytest.raises(ValidationError, match="<none>"):
            validate_extension("README")


# Real magic numbers for the types we touch in tests. PNG and PDF need
# enough bytes for libmagic to commit to the type; "%PDF-…" is enough
# but PNG needs the IHDR chunk to follow the 8-byte signature.
PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"0" * 256
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    + b"\x00\x00\x00\rIHDR"          # IHDR chunk header
    + b"\x00\x00\x00\x01" * 2        # 1x1 px
    + b"\x08\x06\x00\x00\x00"        # 8-bit RGBA, no interlace
    + b"\x1f\x15\xc4\x89"            # CRC of the IHDR
    + b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestValidateContentType:
    """libmagic sniffs the actual bytes; allowlist gates the result."""

    def test_real_pdf_passes(self):
        validate_content_type(_make_file("doc.pdf", PDF_BYTES))

    def test_real_png_passes(self):
        validate_content_type(_make_file("img.png", PNG_BYTES, "image/png"))

    def test_renamed_executable_rejected(self):
        """A file with a PE/Mach-O header but a .pdf extension is caught by sniffing."""
        # MZ is the DOS/Windows executable magic number.
        upload = _make_file("payload.pdf", b"MZ\x90\x00" + b"\x00" * 64,
                            content_type="application/pdf")
        with pytest.raises(ValidationError, match="not allowed"):
            validate_content_type(upload)

    def test_seek_rewinds_for_downstream(self):
        """After sniffing we must leave the file pointer at 0 so save() works."""
        upload = _make_file("doc.pdf", PDF_BYTES)
        validate_content_type(upload)
        assert upload.read() == PDF_BYTES


class TestRunAll:
    """The public entry point chains validators in the documented order."""

    def test_happy_path_passes(self):
        run_all(_make_file("notes.pdf", PDF_BYTES))

    def test_filename_failure_short_circuits_before_libmagic(self):
        """We don't waste a libmagic read on a clearly bad filename."""
        with pytest.raises(ValidationError, match="exactly one extension"):
            run_all(_make_file("foo.pdf.exe", PDF_BYTES))

    @override_settings(PLANLY_MAX_ATTACHMENT_SIZE_MB=1)
    def test_size_failure_short_circuits(self):
        with pytest.raises(ValidationError, match="exceeds"):
            run_all(_make_file("big.pdf", b"x" * 2_000_000))

    def test_extension_failure(self):
        with pytest.raises(ValidationError, match="not allowed"):
            run_all(_make_file("payload.exe", PDF_BYTES))

    def test_content_type_failure(self):
        # Real .pdf extension, real PDF claimed type, but bytes are an executable.
        upload = _make_file("doc.pdf", b"MZ\x90\x00" + b"\x00" * 64)
        with pytest.raises(ValidationError, match="not allowed"):
            run_all(upload)
