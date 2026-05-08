from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ItemForm
from .models import Item


class ItemListView(LoginRequiredMixin, ListView):
    model = Item
    template_name = "example/item_list.html"
    context_object_name = "items"

    def get_queryset(self):
        return Item.objects.for_user(self.request.user)


class ItemDetailView(LoginRequiredMixin, DetailView):
    model = Item
    template_name = "example/item_detail.html"
    context_object_name = "item"

    def get_queryset(self):
        return Item.objects.for_user(self.request.user)


class ItemCreateView(LoginRequiredMixin, CreateView):
    model = Item
    form_class = ItemForm
    template_name = "example/item_form.html"
    success_url = reverse_lazy("example:item-list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ItemUpdateView(LoginRequiredMixin, UpdateView):
    model = Item
    form_class = ItemForm
    template_name = "example/item_form.html"
    success_url = reverse_lazy("example:item-list")

    def get_queryset(self):
        return Item.objects.for_user(self.request.user)


class ItemDeleteView(LoginRequiredMixin, DeleteView):
    model = Item
    template_name = "example/item_confirm_delete.html"
    success_url = reverse_lazy("example:item-list")

    def get_queryset(self):
        return Item.objects.for_user(self.request.user)

    def get_object(self, queryset=None):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
