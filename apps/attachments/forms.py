"""Forms for attachment uploads.

The form exists so HTML upload pages can hand a single object to crispy
for rendering, and so we have one obvious place where every upload —
HTML or future API — runs the same validator stack.
"""

from django import forms
from django.core.exceptions import ValidationError

from .models import Attachment
from .validators import run_all


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ["file"]

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        try:
            run_all(uploaded)
        except ValidationError as exc:
            # The validators raise model-style {"file": "..."} dicts so a
            # model.clean() can attribute the error to the right field.
            # Inside a form's clean_<field> the contract is the opposite:
            # raise the bare message and Django files it under this field
            # automatically. Unwrap once.
            messages = exc.message_dict.get("file") if hasattr(exc, "message_dict") else None
            raise ValidationError(messages or exc.messages) from exc
        return uploaded
