from django.contrib import admin

from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "actor", "verb", "target", "read_at", "created_at"]
    list_filter = ["verb", "read_at"]
    search_fields = ["recipient__email", "recipient__employee_id", "description"]
    autocomplete_fields = ["recipient", "actor"]
    readonly_fields = ["target_content_type", "target_object_id", "target"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "email_on_assignment",
        "email_on_comment",
        "email_on_due_soon",
        "daily_digest",
    ]
    search_fields = ["user__email", "user__employee_id"]
    autocomplete_fields = ["user"]
