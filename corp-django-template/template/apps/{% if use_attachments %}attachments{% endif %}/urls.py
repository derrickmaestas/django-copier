from django.urls import path

from . import views

app_name = "attachments"

urlpatterns = [
    path(
        "item/<int:item_pk>/upload/",
        views.attachment_upload,
        name="attachment-upload",
    ),
    path(
        "<int:pk>/delete/",
        views.attachment_delete,
        name="attachment-delete",
    ),
]
