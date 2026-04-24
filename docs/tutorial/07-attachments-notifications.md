# Chapter 7 — Attachments & Notifications

## Goal

By the end of this chapter you'll have:
- An `Attachment` model with file uploads, size validation, and S3-ready storage
- A `Notification` model using `GenericForeignKey` to link to any object
- A `NotificationPreference` model for per-user delivery settings
- S3 / S3-compatible object storage wired into `production.py`
- Factories and tests for both apps — custom behavior only

This chapter completes the data layer. After this, every domain concept has a model, and we can move on to admin, views, and templates.

---

## Attachments App

Attachments are files uploaded against tasks — design mockups, specs, screenshots, CSV data. The model is small, but the storage configuration is where most of the work is.

### Step 1: The Attachment Model

Create `apps/attachments/models.py`:

```python
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel


def attachment_upload_path(instance: Attachment, filename: str) -> str:
    """Group uploaded files under a per-task directory."""
    return f"attachments/task_{instance.task_id}/{filename}"


class Attachment(TimeStampedModel):
    """A file attached to a task. Stored on S3 in production, local disk in dev."""

    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_attachments",
    )
    file = models.FileField(upload_to=attachment_upload_path)
    filename = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task", "-created_at"], name="idx_attach_task_created"),
        ]

    def __str__(self):
        return self.filename

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)

    def save(self, *args, **kwargs):
        """Derive size_bytes from the uploaded file.

        Reading `file.size` may trigger a backend stat (network call on S3),
        so we do it once at save time and cache the result on the row.
        """
        if self.file:
            self.size_bytes = self.file.size
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        max_bytes = settings.PLANLY_MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
        size = self.file.size if self.file else self.size_bytes
        if size > max_bytes:
            mb = round(size / (1024 * 1024), 2)
            raise ValidationError(
                {
                    "file": (
                        f"File is {mb} MB — "
                        f"exceeds the {settings.PLANLY_MAX_ATTACHMENT_SIZE_MB} MB limit."
                    )
                }
            )
```

### `upload_to` as a Callable

```python
def attachment_upload_path(instance, filename):
    return f"attachments/task_{instance.task_id}/{filename}"

file = models.FileField(upload_to=attachment_upload_path)
```

`upload_to` can be a string like `"attachments/"`, but a callable gives you dynamic paths based on the instance. Our files land at `attachments/task_42/design.pdf`, which makes it easy to find every file for a task and to clean up when a task is deleted.

Never use the user-provided `filename` as the whole path — users can send `../../etc/passwd` as a filename, and Django will dutifully write wherever the string resolves. The prefix we add (`attachments/task_N/`) anchors the path, and Django's default storage will also sanitize the filename.

### Why `size_bytes` as a Separate Field

We could always call `self.file.size` to get the size, but every call hits the storage backend — fast on local disk, a network round-trip on S3. Storing the size at upload time means the "4.2 MB" badge on the task card doesn't cost an S3 API call to render.

The `size_bytes` field uses `PositiveBigIntegerField` rather than `PositiveIntegerField` because `PositiveIntegerField` tops out at 2 GB. `BigInt` goes into the petabytes — overkill today, but it costs nothing and avoids a future migration if the limit ever gets raised.

### Auto-deriving `size_bytes` in `save()`

```python
def save(self, *args, **kwargs):
    if self.file:
        self.size_bytes = self.file.size
    super().save(*args, **kwargs)
```

`size_bytes` is a stored field, but callers shouldn't have to set it — they just hand us a file. Overriding `save()` to derive the value guarantees two things:

1. **Callers can't forget it.** Any code path that creates an `Attachment` (admin upload, API endpoint, management command) gets the right size without having to remember to pass it.
2. **It can't drift from the actual file.** If someone replaces `attachment.file` and saves, the size follows the file — there's no stale value to clean up.

The field keeps `default=0` so the column has a valid value before `save()` runs — otherwise `full_clean()` would complain about a required field that hasn't been populated yet.

Why store it instead of computing from `file.size` every read? Same reason as before: reading `file.size` on S3 is a network call. Storing at save time means every subsequent read is a cheap column fetch.

### Size Validation via `clean()`

```python
def clean(self):
    super().clean()
    max_bytes = settings.PLANLY_MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    size = self.file.size if self.file else self.size_bytes
    if size > max_bytes:
        raise ValidationError(...)
```

`clean()` runs during `Model.full_clean()` and is called by `ModelForm` automatically. Using `clean()` rather than a field-level validator means the error message has access to both the size and the configured limit.

Reading the limit from `settings` (not hardcoding 25) means ops can raise or lower the limit via an environment variable without touching code.

**Why check `self.file.size` before `self.size_bytes`?** `clean()` runs *before* `save()`, so `size_bytes` hasn't been populated yet on a new upload. Reading from the file object catches oversized files before they ever reach the database. On a round-trip edit of an existing attachment, `self.file.size` still works (the file exists in storage), so the same check covers both paths.

**Why not a `FileField` validator?** A `validators=[...]` callback has access to the file only, not the instance. Putting the check on `clean()` lets us read `settings.PLANLY_MAX_ATTACHMENT_SIZE_MB` and include both the actual and allowed sizes in the error message.

### `on_delete` Choices

- **`task` → `CASCADE`**: Deleting a task should delete its attachments. An attachment without a task has nowhere to live.
- **`uploaded_by` → `SET_NULL`**: Deleting a user leaves the file in place. A historical upload is still useful even if the uploader is gone; losing the link to the user is acceptable, losing the file isn't.

---

## Step 2: S3 / S3-Compatible Storage

### The `STORAGES` setting

Django 5+ uses the `STORAGES` setting (replacing the old `DEFAULT_FILE_STORAGE`). Each key defines a named storage backend:

```python
# config/settings/production.py
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": os.environ.get("AWS_STORAGE_BUCKET_NAME", ""),
            "region_name": os.environ.get("AWS_S3_REGION_NAME", "us-east-1"),
            "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL", ""),
            "custom_domain": os.environ.get("AWS_S3_CUSTOM_DOMAIN", ""),
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

- **`"default"`** is what `FileField` and `ImageField` use for uploaded media.
- **`"staticfiles"`** is what `collectstatic` uses. We keep static files on the app server (served by WhiteNoise) because they're small, versioned, and need to be behind CDN edge caches rather than S3.

The dev `local.py` doesn't override `STORAGES` — it inherits Django's default, which writes to `MEDIA_ROOT` on local disk.

### Why `django-storages[s3]`?

Plenty of Django file-storage libraries exist. `django-storages` is the canonical choice because:

- It's maintained by the Django community (not a single company)
- The `[s3]` extra uses `boto3` under the hood — the official AWS SDK
- It works with any S3-compatible service: AWS S3, MinIO (for self-hosted), Cloudflare R2, DigitalOcean Spaces, Backblaze B2

`AWS_S3_ENDPOINT_URL` is the magic setting that unlocks non-AWS providers. For MinIO running locally, you'd set it to `http://minio:9000`. For Cloudflare R2, `https://<account>.r2.cloudflarestorage.com`. Leave it empty to target AWS S3 itself.

### Why Not Store Files in the Database?

PostgreSQL supports `bytea` columns. Django has a `BinaryField`. It's tempting, but don't do it:

- **Bloat** — every `SELECT *` pulls hundreds of MB into memory
- **Backups** — your pg_dump grows linearly with uploads and takes hours instead of seconds
- **Concurrent access** — streaming a 100 MB file out of Postgres blocks a connection; streaming from S3 doesn't touch the app
- **CDN** — S3 integrates with CloudFront and other CDNs natively; a database column doesn't

The only time file-in-database makes sense is for a handful of kilobyte-sized records (a logo, a small avatar) where simplicity beats scale.

---

## Notifications App

Notifications are trickier than attachments. A notification can be *about* anything — a task was assigned, a comment was posted, a plan was shared. A dedicated FK per notification type (`task`, `comment`, `plan`, ...) doesn't scale; every new notifiable object adds a column, most of them NULL.

Django's `contenttypes` framework solves this with a `GenericForeignKey`: a polymorphic reference that can point at any model.

### Step 1: The Notification QuerySet

Create `apps/notifications/querysets.py`:

```python
from django.db import models
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    """Custom queryset for Notification with common scoping helpers."""

    def for_user(self, user):
        return self.filter(recipient=user)

    def unread(self):
        return self.filter(read_at__isnull=True)

    def mark_all_read(self):
        """Bulk-mark all notifications in this queryset as read.

        Uses a single UPDATE — prefer this to iterating and saving each one.
        """
        return self.filter(read_at__isnull=True).update(read_at=timezone.now())
```

**`mark_all_read`** is a queryset method rather than a model method because it acts on a set. `notification.mark_read()` works on one row; `Notification.objects.for_user(request.user).mark_all_read()` issues a single `UPDATE ... WHERE ...`. Looping and calling `mark_read()` on each would produce N queries.

### Step 2: The Notification Model

Create `apps/notifications/models.py`:

```python
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .querysets import NotificationQuerySet


class Notification(TimeStampedModel):
    """An in-app notification.

    Uses a GenericForeignKey to link to any target object (Task, Comment, etc.)
    without a separate FK per type. The `verb` describes what happened
    ("assigned", "commented", "completed").
    """

    class Verb(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        COMMENTED = "commented", "Commented"
        COMPLETED = "completed", "Completed"
        MENTIONED = "mentioned", "Mentioned"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="actor_notifications",
    )
    verb = models.CharField(max_length=20, choices=Verb.choices)
    description = models.CharField(max_length=255, blank=True)

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    target_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    read_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "-created_at"],
                name="idx_notif_recipient_created",
            ),
            models.Index(
                fields=["recipient", "read_at"],
                name="idx_notif_unread",
                condition=models.Q(read_at__isnull=True),
            ),
        ]

    def __str__(self):
        return f"{self.actor} {self.verb} → {self.recipient}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self) -> None:
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])
```

### GenericForeignKey — The Three-Field Pattern

```python
target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
target_object_id = models.PositiveBigIntegerField(null=True, blank=True)
target = GenericForeignKey("target_content_type", "target_object_id")
```

A `GenericForeignKey` is three fields in a trench coat:

1. **`target_content_type`** — a FK to `ContentType`, which is Django's registry of every model. This identifies *which model* the target belongs to.
2. **`target_object_id`** — the PK of the target row.
3. **`target`** — a descriptor (not a real database column) that gives you the actual object: `notification.target` returns a `Task` if the target is a task, a `Comment` if it's a comment, etc.

Usage:

```python
# Create a notification about a task
Notification.objects.create(
    recipient=assignee,
    actor=request.user,
    verb=Notification.Verb.ASSIGNED,
    target=task,   # GenericForeignKey auto-fills content_type + object_id
)

# Later, in a template or view
notification.target  # returns the Task instance
```

**The trade-off**: no FK constraint at the database level. Postgres can't enforce that `target_object_id` corresponds to a real row — the integrity is managed in Python. Don't use `GenericForeignKey` for structural relationships (a task belongs to a bucket, full stop). Use it for loose pointers where flexibility matters more than strict integrity — exactly the case for notifications.

### `read_at` Timestamp vs `is_read` Boolean

```python
read_at = models.DateTimeField(null=True, blank=True)

@property
def is_read(self) -> bool:
    return self.read_at is not None
```

Storing `read_at` instead of `is_read` buys you two things:

1. **When was it read?** Useful for analytics ("notifications are taking 3 days to be acknowledged") and for replaying timelines.
2. **Free boolean** — `read_at IS NOT NULL` serves as the boolean. You don't have two fields to keep in sync.

The partial index `idx_notif_unread` (with `condition=Q(read_at__isnull=True)`) only indexes unread rows. Most queries want unread notifications for the bell icon; read notifications accumulate forever and shouldn't bloat the index.

### Actor vs Recipient

- **`recipient`** — the person being notified. `CASCADE` because a notification belongs to its recipient; if the user is deleted, their notifications go too.
- **`actor`** — the person who did the thing. `SET_NULL` because the notification text is still valuable even if the actor is gone ("someone commented on your task" is better than losing the notification entirely).

### Step 3: NotificationPreference

```python
class NotificationPreference(TimeStampedModel):
    """Per-user toggles for notification delivery channels and categories."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
    )
    email_on_assignment = models.BooleanField(default=True)
    email_on_comment = models.BooleanField(default=True)
    email_on_due_soon = models.BooleanField(default=True)
    daily_digest = models.BooleanField(default=False)

    def __str__(self):
        return f"Preferences for {self.user}"
```

`OneToOneField` is a `ForeignKey` with `unique=True`. Each user has at most one preference row, enforced at the database level.

**Why a separate model?** We could add these booleans directly to the `User` model. Keeping them separate has two benefits:

- **Lazy creation** — you don't need a row for every user. A user who never opens preferences implicitly uses the defaults.
- **Schema stability** — adding or renaming preference toggles doesn't touch the `User` table, which is referenced by every other model via `AUTH_USER_MODEL`.

### Why start booleans as True?

Defaulting notifications on is an intentional choice. Users who *want* notifications get them without any setup; users who don't want them flip a switch once. If we defaulted off, first-time users would silently miss assignments. The one we default off — `daily_digest` — is off because it's additive (in addition to real-time notifications) and most people find daily digests noisy.

---

## Step 4: Factories and Tests

### Attachment factory

Create `apps/attachments/tests/factories.py`:

```python
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
    content_type = "text/plain"
    file = factory.LazyAttribute(
        lambda obj: SimpleUploadedFile(obj.filename, b"test content")
    )
```

**`SimpleUploadedFile`** is Django's in-memory stand-in for a `TemporaryUploadedFile`. Tests shouldn't write to real disk — `SimpleUploadedFile` gives the model a file-like object that satisfies `FileField` without touching the filesystem.

Note there's no `size_bytes` default on the factory — `save()` derives it from whatever file the factory supplies. If a test needs a specific size, it can override `file=` with a payload of the desired length.

### Attachment tests

Create `apps/attachments/tests/test_models.py`:

```python
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.attachments.tests.factories import AttachmentFactory


@pytest.mark.django_db
class TestAttachmentStr:
    def test_str(self):
        attachment = AttachmentFactory(filename="report.pdf")
        assert str(attachment) == "report.pdf"


@pytest.mark.django_db
class TestAttachmentSave:
    def test_size_bytes_auto_set_from_file(self):
        payload = b"x" * 4096
        attachment = AttachmentFactory(
            file=SimpleUploadedFile("data.bin", payload),
        )
        assert attachment.size_bytes == len(payload)

    def test_size_bytes_refreshes_when_file_changes(self):
        attachment = AttachmentFactory(file=SimpleUploadedFile("a.bin", b"a" * 100))
        assert attachment.size_bytes == 100

        attachment.file = SimpleUploadedFile("b.bin", b"b" * 500)
        attachment.save()
        assert attachment.size_bytes == 500


@pytest.mark.django_db
class TestAttachmentSizeMb:
    def test_converts_bytes_to_mb(self):
        attachment = AttachmentFactory.build(size_bytes=5 * 1024 * 1024)
        assert attachment.size_mb == 5.0

    def test_rounds_to_two_decimals(self):
        attachment = AttachmentFactory.build(size_bytes=1_500_000)
        assert attachment.size_mb == 1.43


@pytest.mark.django_db
class TestAttachmentCleanSizeLimit:
    @override_settings(PLANLY_MAX_ATTACHMENT_SIZE_MB=1)
    def test_rejects_oversized_file(self):
        attachment = AttachmentFactory.build(
            file=SimpleUploadedFile("big.bin", b"x" * (2 * 1024 * 1024)),
        )
        with pytest.raises(ValidationError) as exc:
            attachment.clean()
        assert "exceeds" in str(exc.value)

    @override_settings(PLANLY_MAX_ATTACHMENT_SIZE_MB=5)
    def test_accepts_file_at_limit(self):
        attachment = AttachmentFactory.build(
            file=SimpleUploadedFile("ok.bin", b"x" * (5 * 1024 * 1024)),
        )
        attachment.clean()  # should not raise
```

**`TestAttachmentSave`** covers the new auto-set behavior directly: create with a known-size payload, assert the stored `size_bytes` matches; then swap the file and confirm `size_bytes` updates on re-save.

**`TestAttachmentSizeMb`** uses `.build()` because `save()` would overwrite the explicit `size_bytes` by deriving it from the 12-byte `SimpleUploadedFile`. `build()` skips the save and lets us test the property in isolation.

**`TestAttachmentCleanSizeLimit`** now constructs an actual oversized `SimpleUploadedFile`, because `clean()` reads from `self.file.size` rather than a pre-populated `size_bytes`.

**`@override_settings`** temporarily changes settings for a test. The limit is read from `settings.PLANLY_MAX_ATTACHMENT_SIZE_MB` at call time, so overriding it in the test lets us check the validator without relying on whatever value is configured globally.

**`AttachmentFactory.build(...)`** (not `AttachmentFactory(...)`) creates the instance *without* saving. `clean()` doesn't need a saved row, and skipping the save avoids writing the `SimpleUploadedFile` to the test media directory.

### Notification factories and tests

Create `apps/notifications/tests/factories.py`:

```python
import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification, NotificationPreference


class NotificationFactory(DjangoModelFactory):
    class Meta:
        model = Notification

    recipient = factory.SubFactory(UserFactory)
    actor = factory.SubFactory(UserFactory)
    verb = Notification.Verb.ASSIGNED
    description = ""


class NotificationPreferenceFactory(DjangoModelFactory):
    class Meta:
        model = NotificationPreference

    user = factory.SubFactory(UserFactory)
```

Create `apps/notifications/tests/test_models.py`:

```python
import pytest

from apps.notifications.tests.factories import (
    NotificationFactory,
    NotificationPreferenceFactory,
)


@pytest.mark.django_db
class TestNotificationStr:
    def test_str(self):
        notification = NotificationFactory(verb="assigned")
        expected = f"{notification.actor} assigned → {notification.recipient}"
        assert str(notification) == expected


@pytest.mark.django_db
class TestNotificationIsRead:
    def test_unread_by_default(self):
        notification = NotificationFactory()
        assert notification.is_read is False

    def test_read_when_read_at_set(self):
        notification = NotificationFactory()
        notification.mark_read()
        assert notification.is_read is True


@pytest.mark.django_db
class TestNotificationMarkRead:
    def test_sets_read_at_timestamp(self):
        notification = NotificationFactory()
        assert notification.read_at is None

        notification.mark_read()
        notification.refresh_from_db()

        assert notification.read_at is not None

    def test_idempotent(self):
        """Calling mark_read twice should not overwrite the original timestamp."""
        notification = NotificationFactory()
        notification.mark_read()
        first_timestamp = notification.read_at

        notification.mark_read()
        notification.refresh_from_db()

        assert notification.read_at == first_timestamp


@pytest.mark.django_db
class TestNotificationPreferenceStr:
    def test_str(self):
        pref = NotificationPreferenceFactory()
        assert str(pref) == f"Preferences for {pref.user}"
```

The `test_idempotent` case matters because `mark_read()` includes an `if self.read_at is None` guard. Without that guard, calling `mark_read()` on an already-read notification would update the timestamp to "now" and lose the original read time — the exact thing we store `read_at` to preserve.

Create `apps/notifications/tests/test_querysets.py`:

```python
import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory


@pytest.mark.django_db
class TestNotificationQuerySetForUser:
    def test_returns_recipients_notifications(self):
        user = UserFactory()
        notification = NotificationFactory(recipient=user)

        result = Notification.objects.for_user(user)

        assert notification in result

    def test_excludes_other_users_notifications(self):
        NotificationFactory()
        other_user = UserFactory()

        result = Notification.objects.for_user(other_user)

        assert result.count() == 0


@pytest.mark.django_db
class TestNotificationQuerySetUnread:
    def test_returns_notifications_without_read_at(self):
        notification = NotificationFactory()

        assert notification in Notification.objects.unread()

    def test_excludes_read_notifications(self):
        notification = NotificationFactory(read_at=timezone.now())

        assert notification not in Notification.objects.unread()


@pytest.mark.django_db
class TestNotificationQuerySetMarkAllRead:
    def test_sets_read_at_on_all_unread(self):
        user = UserFactory()
        NotificationFactory(recipient=user)
        NotificationFactory(recipient=user)

        Notification.objects.for_user(user).mark_all_read()

        assert Notification.objects.for_user(user).unread().count() == 0

    def test_does_not_overwrite_existing_read_at(self):
        """Already-read notifications keep their original read_at timestamp."""
        user = UserFactory()
        original = timezone.now()
        read_notification = NotificationFactory(recipient=user, read_at=original)

        Notification.objects.for_user(user).mark_all_read()

        read_notification.refresh_from_db()
        assert read_notification.read_at == original
```

`test_does_not_overwrite_existing_read_at` protects the invariant that `mark_all_read` only writes to rows that are actually unread. The `.filter(read_at__isnull=True)` in the queryset is what enforces this, and the test would catch any future refactor that drops it.

---

## Step 5: Generate Migrations

```bash
docker compose run --rm --user root web uv run python manage.py makemigrations attachments notifications
```

You should see:

```
Migrations for 'attachments':
  apps/attachments/migrations/0001_initial.py
    + Create model Attachment
Migrations for 'notifications':
  apps/notifications/migrations/0001_initial.py
    + Create model NotificationPreference
    + Create model Notification
```

### Why `--user root` for makemigrations?

The runtime container runs as the non-root `planly` user (for security). `/app` is owned by root, so `planly` can read files but can't write new ones. `makemigrations` needs to write migration files back to disk. `--user root` overrides the user for this one command — the generated files end up on the host via the bind mount.

Day-to-day code changes don't need this: editing models happens on the host, Compose watch syncs the new `models.py` into the container, and `migrate` only reads migrations. It's only `makemigrations` — a file-writing command — that needs the override.

### Why this is safe

Migration files are generated from model definitions — not from arbitrary user input or container state. Running `makemigrations` as root briefly to produce deterministic, reviewable Python files is a very different risk profile from running the *application* as root, which we still don't.

---

## Step 6: Run the Tests

```bash
docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test web uv run pytest
```

All tests should pass.

---

## Checkpoint

Before moving on, verify:

- [ ] `uv run pytest -v` passes all tests
- [ ] `uv run ruff check apps/ config/` reports no lint errors
- [ ] Migrations exist for both apps: `apps/attachments/migrations/0001_initial.py` and `apps/notifications/migrations/0001_initial.py`
- [ ] `config/settings/production.py` has `STORAGES["default"]` pointing at `S3Boto3Storage`

**Next:** [Chapter 8 — Admin & Data Exploration](08-admin-data-exploration.md)
