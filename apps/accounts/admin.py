from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.notifications.models import NotificationPreference

from .models import Discipline, Membership, Team, User


class NotificationPreferenceInline(admin.StackedInline):
    model = NotificationPreference
    can_delete = False
    extra = 0
    verbose_name_plural = "Notification preferences"


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["employee_id"]
    list_display = [
        "employee_id",
        "email",
        "display_name",
        "discipline",
        "is_manager",
        "is_staff",
    ]
    list_filter = ["is_staff", "is_superuser", "is_active", "is_manager", "discipline"]
    search_fields = ["employee_id", "email", "display_name"]
    autocomplete_fields = ["discipline"]
    inlines = [NotificationPreferenceInline]

    fieldsets = (
        (None, {"fields": ("employee_id", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "email",
                    "display_name",
                    "division",
                    "organization",
                    "discipline",
                    "is_manager",
                ),
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("employee_id", "email", "password1", "password2"),
            },
        ),
    )


@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created_at"]
    search_fields = ["name"]
    autocomplete_fields = ["owner"]
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "team", "role", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__employee_id", "user__email", "team__name"]
    autocomplete_fields = ["user", "team"]
