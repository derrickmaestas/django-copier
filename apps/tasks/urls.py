from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("buckets/<int:bucket_pk>/create/", views.TaskCreateView.as_view(), name="task-create"),
    path("<int:pk>/", views.TaskDetailView.as_view(), name="task-detail"),
    path("<int:pk>/edit/", views.TaskUpdateView.as_view(), name="task-update"),
    path("<int:pk>/delete/", views.TaskDeleteView.as_view(), name="task-delete"),
    path("<int:pk>/complete/", views.task_mark_complete, name="task-complete"),
    path(
        "plans/<int:plan_pk>/labels/create/",
        views.LabelCreateView.as_view(),
        name="label-create",
    ),
    path("labels/<int:pk>/edit/", views.LabelUpdateView.as_view(), name="label-update"),
    path("labels/<int:pk>/delete/", views.LabelDeleteView.as_view(), name="label-delete"),
    path(
        "<int:task_pk>/checklist/add/",
        views.checklist_item_add,
        name="checklist-item-add",
    ),
    path(
        "checklist/<int:pk>/toggle/",
        views.checklist_item_toggle,
        name="checklist-item-toggle",
    ),
    path(
        "checklist/<int:pk>/delete/",
        views.checklist_item_delete,
        name="checklist-item-delete",
    ),
    path("<int:task_pk>/comments/add/", views.comment_add, name="comment-add"),
]
