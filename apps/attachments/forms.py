"""Forms for attachment uploads.

The form exists so HTML upload pages can hand a single object to crispy
for rendering, and so we have one obvious place where every upload —
HTML or future API — runs the same validator stack.
"""

from django import forms

from .models import Attachment
from .validators import run_all


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ["file"]

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        run_all(uploaded)
        return uploaded
