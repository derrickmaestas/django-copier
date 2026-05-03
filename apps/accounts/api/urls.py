"""URL routes contributed by the accounts app to /api/v1/.

`me/` is a singleton endpoint (not a collection of users), so it's a
plain APIView rather than a ViewSet — there's no list/retrieve/create
distinction to model. Listing or creating users is intentionally not
exposed; user accounts are managed by the admin/HR side, not the API.
"""

from django.urls import path

from .views import MeView

urlpatterns = [
    path("me/", MeView.as_view(), name="user-me"),
]
