"""Session-wide pytest fixtures shared across all apps.

The chief job here is creating real database tables for the test-only
concrete models declared in `apps/core/tests/test_models.py` — those
models exist solely to exercise the abstract bases (`TimeStampedModel`,
`OrderedModel`) and have no migrations of their own.

The test suite runs with migrations enabled. That means Django's syncdb
path no longer auto-creates tables for installed-but-unmigrated test
models. This fixture fills the gap.
"""

import pytest
from django.db import connection


@pytest.fixture(scope="session", autouse=True)
def _create_abstract_base_test_tables(django_db_setup, django_db_blocker):
    """Create tables for the concrete test models in apps/core/tests/test_models.py."""
    from apps.core.tests.test_models import (
        ConcreteOrdered,
        ConcreteTimeStamped,
        ConcreteTimeStampedOrdered,
    )

    test_only_models = [
        ConcreteTimeStamped,
        ConcreteOrdered,
        ConcreteTimeStampedOrdered,
    ]

    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        for model in test_only_models:
            editor.create_model(model)

    yield

    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        for model in reversed(test_only_models):
            editor.delete_model(model)
