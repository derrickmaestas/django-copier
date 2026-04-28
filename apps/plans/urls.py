from django.urls import path

from . import views

app_name = "plans"

urlpatterns = [
    path("", views.PlanListView.as_view(), name="plan-list"),
    path("create/", views.PlanCreateView.as_view(), name="plan-create"),
    path("<int:pk>/", views.PlanDetailView.as_view(), name="plan-detail"),
    path("<int:pk>/edit/", views.PlanUpdateView.as_view(), name="plan-update"),
    path("<int:pk>/delete/", views.PlanDeleteView.as_view(), name="plan-delete"),
    path(
        "<int:plan_pk>/buckets/create/",
        views.BucketCreateView.as_view(),
        name="bucket-create",
    ),
    path(
        "buckets/<int:pk>/edit/",
        views.BucketUpdateView.as_view(),
        name="bucket-update",
    ),
    path(
        "buckets/<int:pk>/delete/",
        views.BucketDeleteView.as_view(),
        name="bucket-delete",
    ),
]
