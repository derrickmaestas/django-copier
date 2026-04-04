from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model — placeholder, will be expanded in Chapter 5."""

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.username
