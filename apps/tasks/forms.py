import re

from django import forms

from .models import ChecklistItem, Comment, Label, Task

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class TaskForm(forms.ModelForm):
    """Form for creating or editing a Task.

    Past due dates are allowed — Microsoft Planner labels them "Late"
    rather than block creation, which matches how people actually log
    catch-up work.
    """

    class Meta:
        model = Task
        fields = ["title", "description", "priority", "progress", "due_date", "start_date"]

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        due = cleaned.get("due_date")
        if start and due and start > due:
            raise forms.ValidationError(
                {"start_date": "Start date must be on or before the due date."},
            )
        return cleaned


class TaskCreateForm(TaskForm):
    """Task form variant used by TaskCreateView — no `progress` field.

    Newly-created tasks always start at NOT_STARTED; exposing progress on
    the create form is a footgun.
    """

    class Meta(TaskForm.Meta):
        fields = ["title", "description", "priority", "due_date", "start_date"]


class LabelForm(forms.ModelForm):
    """Form for creating or editing a Label within a known Plan.

    The plan is supplied by the view (resolved from the URL), so it isn't
    exposed to the user. Color is validated as a 6-digit hex code.
    """

    class Meta:
        model = Label
        fields = ["name", "color"]

    def clean_color(self):
        color = self.cleaned_data["color"].strip()
        if not HEX_COLOR_RE.match(color):
            raise forms.ValidationError("Color must be a 6-digit hex code (e.g. #6B7280).")
        return color


class ChecklistItemForm(forms.ModelForm):
    """Form for adding a checklist item to a known Task.

    The task is supplied by the view, and position is auto-set on create.
    """

    class Meta:
        model = ChecklistItem
        fields = ["title"]


class CommentForm(forms.ModelForm):
    """Form for adding a comment to a known Task.

    The task and author are supplied by the view.
    """

    class Meta:
        model = Comment
        fields = ["body"]
