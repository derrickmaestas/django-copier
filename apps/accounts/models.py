from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import TimeStampedModel


class User(AbstractUser, TimeStampedModel):
    """Custom user model with employee profile fields."""

    employee_id = models.PositiveIntegerField(unique=True)
    display_name = models.CharField(max_length=255, blank=True)
    division = models.CharField(max_length=255, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    team = models.CharField(max_length=255, blank=True)
    is_manager = models.BooleanField(default=False)

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.username


class Team(TimeStampedModel):
    """A group of users who collaborate on plans."""

    name = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_teams",
    )
    members = models.ManyToManyField(
        User,
        through="Membership",
        related_name="teams",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    """Explicit M2M through model linking users to teams with roles."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        ordering = ["user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"],
                name="unique_team_member",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.team.name} ({self.role})"
