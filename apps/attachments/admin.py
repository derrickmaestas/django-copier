from django.contrib import admin

from .models import Attachment


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ["filename", "task", "uploaded_by", "size_mb", "created_at"]
    search_fields = ["filename", "task__title"]
    autocomplete_fields = ["task", "uploaded_by"]
    readonly_fields = ["size_bytes", "size_mb", "content_type"]

    @admin.display(description="Size (MB)")
    def size_mb(self, obj):
        return obj.size_mb
