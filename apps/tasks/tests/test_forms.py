import datetime

import pytest

from apps.tasks.forms import LabelForm, TaskForm
from apps.tasks.models import Task


@pytest.mark.django_db
class TestLabelForm:
    def test_invalid_hex_color_rejected(self):
        form = LabelForm(data={"name": "Bug", "color": "red"})
        assert not form.is_valid()
        assert "color" in form.errors

    def test_short_hex_color_rejected(self):
        form = LabelForm(data={"name": "Bug", "color": "#FFF"})
        assert not form.is_valid()
        assert "color" in form.errors

    def test_lowercase_hex_color_accepted(self):
        form = LabelForm(data={"name": "Bug", "color": "#abcdef"})
        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestTaskFormDateValidation:
    def _base_data(self, **overrides):
        data = {
            "title": "A task",
            "description": "",
            "priority": Task.Priority.MEDIUM,
            "progress": Task.Progress.NOT_STARTED,
            "due_date": "",
            "start_date": "",
        }
        data.update(overrides)
        return data

    def test_start_date_after_due_date_invalid(self):
        form = TaskForm(
            data=self._base_data(
                start_date=datetime.date(2026, 5, 10),
                due_date=datetime.date(2026, 5, 1),
            ),
        )
        assert not form.is_valid()
        assert "start_date" in form.errors

    def test_start_date_equals_due_date_valid(self):
        same_day = datetime.date(2026, 5, 1)
        form = TaskForm(
            data=self._base_data(start_date=same_day, due_date=same_day),
        )
        assert form.is_valid(), form.errors

    def test_only_one_date_set_is_fine(self):
        # Common Planner workflow — only due_date, no start_date.
        form = TaskForm(data=self._base_data(due_date=datetime.date(2026, 5, 1)))
        assert form.is_valid(), form.errors

    def test_past_due_date_is_allowed(self):
        # Planner-style: backdating completed work is legitimate.
        form = TaskForm(data=self._base_data(due_date=datetime.date(2020, 1, 1)))
        assert form.is_valid(), form.errors
