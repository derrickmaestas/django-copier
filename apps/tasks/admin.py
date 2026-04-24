from django.contrib import admin

from apps.attachments.models import Attachment

from .models import Assignment, ChecklistItem, Comment, Label, Task


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    autocomplete_fields = ["user"]


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0
    fields = ["position", "title", "is_completed"]
    ordering = ["position"]


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ["created_by", "body", "created_at"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["created_by"]


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ["filename", "uploaded_by", "size_bytes", "content_type", "created_at"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["uploaded_by"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "bucket", "priority", "progress", "due_date", "created_at"]
    list_filter = ["priority", "progress", "bucket__plan"]
    search_fields = ["title", "description"]
    autocomplete_fields = ["bucket", "created_by", "labels"]
    date_hierarchy = "due_date"
    inlines = [AssignmentInline, ChecklistItemInline, CommentInline, AttachmentInline]


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ["name", "plan", "color"]
    list_filter = ["plan"]
    search_fields = ["name", "plan__title"]
    autocomplete_fields = ["plan"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["task", "created_by", "created_at"]
    search_fields = ["body", "task__title"]
    autocomplete_fields = ["task", "created_by"]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ["task", "user", "created_at"]
    search_fields = ["task__title", "user__employee_id", "user__email"]
    autocomplete_fields = ["task", "user"]


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ["title", "task", "position", "is_completed"]
    list_filter = ["is_completed"]
    search_fields = ["title", "task__title"]
    autocomplete_fields = ["task"]
