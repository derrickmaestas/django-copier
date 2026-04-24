from django.contrib import admin

from .models import Bucket, Plan


class BucketInline(admin.TabularInline):
    model = Bucket
    extra = 0
    fields = ["position", "title"]
    ordering = ["position"]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["title", "team", "owner", "visibility", "created_at"]
    list_filter = ["visibility", "team"]
    search_fields = ["title", "description"]
    autocomplete_fields = ["team", "owner", "created_by"]
    inlines = [BucketInline]


@admin.register(Bucket)
class BucketAdmin(admin.ModelAdmin):
    list_display = ["title", "plan", "position"]
    list_filter = ["plan"]
    search_fields = ["title", "plan__title"]
    autocomplete_fields = ["plan"]
