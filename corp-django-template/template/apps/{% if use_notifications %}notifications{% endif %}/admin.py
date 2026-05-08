from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "actor", "verb", "target", "read_at", "created_at"]
    list_filter = ["verb", "read_at"]
    search_fields = ["recipient__email", "recipient__employee_id", "description"]
    autocomplete_fields = ["recipient", "actor"]
    readonly_fields = ["target_content_type", "target_object_id", "target"]
