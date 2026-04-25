from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("buckets/<int:bucket_pk>/create/", views.TaskCreateView.as_view(), name="task-create"),
    path("<int:pk>/", views.TaskDetailView.as_view(), name="task-detail"),
    path("<int:pk>/edit/", views.TaskUpdateView.as_view(), name="task-update"),
    path("<int:pk>/delete/", views.TaskDeleteView.as_view(), name="task-delete"),
    path("<int:pk>/complete/", views.task_mark_complete, name="task-complete"),
]
