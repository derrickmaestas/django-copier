"""Views for the attachment upload UI.

The upload form on the task detail page POSTs here; HTMX swaps the
returned partial into the attachment list on success. Both views
team-scope through `for_user()` so non-members get 404, never 403.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.tasks.models import Task

from .forms import AttachmentForm
from .models import Attachment


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


@login_required
@require_POST
def attachment_upload(request, task_pk):
    """Handle the file upload, run validators, persist, render partial.

    `AttachmentForm.clean_file` runs the full validator stack (size cap,
    extension allowlist, libmagic content-type sniff, filename safety).
    A failed validation re-renders the upload section with errors;
    HTMX clients get a 422 so the form can show the error inline
    without replacing the page.
    """
    task = get_object_or_404(Task.objects.for_user(request.user), pk=task_pk)
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.task = task
        attachment.uploaded_by = request.user
        # Mirror what the model.save() override needs to know — the
        # filename a human typed (which can include the original name
        # with spaces) is stored separately from the storage path.
        attachment.filename = form.cleaned_data["file"].name
        attachment.content_type = form.cleaned_data["file"].content_type or ""
        attachment.save()
        if _is_htmx(request):
            return render(
                request,
                "tasks/task_detail.html#attachment_item",
                {"attachment": attachment},
            )
        return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))

    # Validation failed.
    if _is_htmx(request):
        # Render the upload form (not the list) so the field-level
        # error messages from clean_file show up next to the input.
        return render(
            request,
            "tasks/task_detail.html#attachment_form_errors",
            {"task": task, "form": form},
            status=422,
        )
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task.pk}))


@login_required
@require_POST
def attachment_delete(request, pk):
    """Delete an attachment; team-scoped so non-members get 404.

    Returns an empty 200 to HTMX so an outerHTML swap removes the
    matching <li> from the DOM. Non-HTMX clients are redirected to
    the parent task's detail page.
    """
    attachment = get_object_or_404(
        Attachment.objects.for_user(request.user),
        pk=pk,
    )
    task_pk = attachment.task_id
    # FileField.delete() removes the underlying storage object; without
    # it the row goes but the file lingers in S3 / disk forever.
    attachment.file.delete(save=False)
    attachment.delete()
    if _is_htmx(request):
        return HttpResponse(status=200)
    return HttpResponseRedirect(reverse("tasks:task-detail", kwargs={"pk": task_pk}))
