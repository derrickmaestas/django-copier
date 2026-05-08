from django.contrib import admin

from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["name", "team", "created_by", "created_at"]
    list_filter = ["team"]
    search_fields = ["name", "description"]
    autocomplete_fields = ["team", "created_by"]
