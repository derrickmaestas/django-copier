{%- if use_notifications %}
from django.apps import AppConfig


class ExampleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.example"
    label = "example"
    verbose_name = "Example"

    def ready(self):
        from . import signals  # noqa: F401
{%- else %}
from django.apps import AppConfig


class ExampleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.example"
    label = "example"
    verbose_name = "Example"
{%- endif %}
