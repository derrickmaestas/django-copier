from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 25

    def get_queryset(self):
        return Notification.objects.for_user(self.request.user).select_related("actor")


@login_required
@require_POST
def notification_mark_read(request, pk):
    notification = get_object_or_404(
        Notification.objects.for_user(request.user),
        pk=pk,
    )
    notification.mark_read()
    return HttpResponseRedirect(reverse("notifications:notification-list"))


@login_required
@require_POST
def notification_mark_all_read(request):
    Notification.objects.for_user(request.user).mark_all_read()
    return HttpResponseRedirect(reverse("notifications:notification-list"))
