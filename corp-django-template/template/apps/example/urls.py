from django.urls import path

from . import views

app_name = "example"

urlpatterns = [
    path("", views.ItemListView.as_view(), name="item-list"),
    path("create/", views.ItemCreateView.as_view(), name="item-create"),
    path("<int:pk>/", views.ItemDetailView.as_view(), name="item-detail"),
    path("<int:pk>/edit/", views.ItemUpdateView.as_view(), name="item-edit"),
    path("<int:pk>/delete/", views.ItemDeleteView.as_view(), name="item-delete"),
]
