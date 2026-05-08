"""Forms for attachment uploads.

Single place where every upload — HTML or future API — runs the same
validator stack from validators.py.
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
            messages = exc.message_dict.get("file") if hasattr(exc, "message_dict") else None
            raise ValidationError(messages or exc.messages) from exc
        return uploaded
