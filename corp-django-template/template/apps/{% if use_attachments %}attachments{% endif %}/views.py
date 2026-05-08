"""Views for the attachment upload UI.

The base shape is here — the consumer wires up the per-target upload
URL once they know what model attachments hang off in their domain.
For the placeholder Item app, attachments hang off Item; the consumer
swaps the import + queryset target when they replace apps/example.
"""

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

# The placeholder uses Item; swap this when you replace apps/example.
from apps.example.models import Item

from .forms import AttachmentForm
from .models import Attachment


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


@login_required
@require_POST
def attachment_upload(request, item_pk):
    """Upload a file to an Item. Team-scoped via for_user()."""
    item = get_object_or_404(Item.objects.for_user(request.user), pk=item_pk)
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.target_content_type = ContentType.objects.get_for_model(Item)
        attachment.target_object_id = item.pk
        attachment.uploaded_by = request.user
        attachment.filename = form.cleaned_data["file"].name
        attachment.content_type = form.cleaned_data["file"].content_type or ""
        attachment.save()
    return HttpResponseRedirect(reverse("example:item-detail", kwargs={"pk": item.pk}))


@login_required
@require_POST
def attachment_delete(request, pk):
    """Delete an attachment."""
    attachment = get_object_or_404(Attachment, pk=pk, uploaded_by=request.user)
    target_pk = attachment.target_object_id
    attachment.file.delete(save=False)
    attachment.delete()
    if _is_htmx(request):
        return HttpResponse(status=200)
    return HttpResponseRedirect(reverse("example:item-detail", kwargs={"pk": target_pk}))
