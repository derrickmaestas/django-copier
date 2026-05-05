r"""Server-side validation for attachment uploads.

Centralized here so the form, the API serializer (when it lands), and any
future bulk-import path all run the same checks. Each validator raises a
`ValidationError` keyed to the `file` field — the form/serializer
surfaces the message verbatim.

What we check, in order:

1. **Filename safety** — reject path separators (`/`, `\`), null bytes,
   leading dots, and names with multiple extensions (`invoice.pdf.exe`).
2. **Size** — refuse files over PLANLY_MAX_ATTACHMENT_SIZE_MB. The cap
   stops a single user from filling the bucket.
3. **Extension allowlist** — only the kinds we deliberately support.
4. **MIME sniff vs claimed type** — read the first kilobytes with
   libmagic and reject anything whose actual content type isn't in the
   allowlist. Stops the rename-to-pdf upload trick where a `.pdf` file
   actually contains an executable payload.
"""

from __future__ import annotations

import magic
from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = frozenset({
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".txt", ".md", ".csv", ".json",
    ".zip",
})

# MIME types we trust for each extension. Only one direction needs to be
# tight — the *sniffed* type is what we authenticate the file by; the
# claimed type from the browser is informational.
ALLOWED_MIME_TYPES = frozenset({
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml",
    "text/plain", "text/markdown", "text/csv", "application/json",
    "application/zip",
})

# How many bytes libmagic needs to identify a file. 8 KiB is plenty for
# every signature in our allowlist and keeps memory bounded for huge
# uploads — we sniff the head, not the body.
SNIFF_BYTES = 8192


def validate_filename(name: str) -> None:
    """Reject filenames that try to escape the upload directory or hide an exe."""
    if not name:
        raise ValidationError({"file": "Uploads must have a filename."})
    if "/" in name or "\\" in name or "\x00" in name:
        raise ValidationError({"file": "Filename contains illegal characters."})
    if name.startswith("."):
        raise ValidationError({"file": "Filename must not start with a dot."})
    # Two or more dots in the *base* name (`report.tar.gz` → 2, but
    # `image.JPG.exe` is the case we care about). We allow exactly one
    # extension; anything else is suspicious and rejected.
    if name.count(".") != 1:
        raise ValidationError(
            {"file": "Filename must have exactly one extension."}
        )


def validate_size(uploaded_file) -> None:
    max_bytes = settings.PLANLY_MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_bytes:
        mb = round(uploaded_file.size / (1024 * 1024), 2)
        raise ValidationError(
            {
                "file": (
                    f"File is {mb} MB — "
                    f"exceeds the {settings.PLANLY_MAX_ATTACHMENT_SIZE_MB} MB limit."
                )
            }
        )


def validate_extension(name: str) -> None:
    # `.lower()` so `Photo.JPG` is treated the same as `photo.jpg`.
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            {"file": f"Files of type {suffix or '<none>'} are not allowed."}
        )


def validate_content_type(uploaded_file) -> None:
    """Sniff the actual content type and require it to be in the allowlist.

    Uses libmagic — the same tool `file(1)` uses — so a renamed `.exe`
    declared as `application/pdf` is caught by mismatching the bytes we
    see at the start of the upload.
    """
    head = uploaded_file.read(SNIFF_BYTES)
    uploaded_file.seek(0)  # rewind so the rest of the upload pipeline still works
    sniffed = magic.from_buffer(head, mime=True)
    if sniffed not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            {"file": f"Detected content type {sniffed!r} is not allowed."}
        )


def run_all(uploaded_file) -> None:
    """Run every validator in the order listed at the top of the module.

    Order matters — cheap checks (filename, size) run before the libmagic
    read so a malformed or oversized upload is rejected before we touch
    the file body.
    """
    validate_filename(uploaded_file.name)
    validate_size(uploaded_file)
    validate_extension(uploaded_file.name)
    validate_content_type(uploaded_file)
