from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.plans.models import Bucket, Plan

from .permissions import IsTeamOwnerOrAdmin
from .serializers import BucketSerializer, PlanSerializer


class PlanViewSet(viewsets.ModelViewSet):
    """CRUD for Plans, scoped to the user's team memberships.

    The `for_user(request.user)` filter in `get_queryset()` is the
    primary defense — non-members can't list, retrieve, update, or
    delete plans they aren't a member of (lookup falls through to a
    404, never a 403, so we don't leak object existence).

    On create, `created_by` is stamped from the request; clients
    declare which `team` the plan belongs to. The serializer enforces
    `created_by` as read-only, so the field can't be spoofed.
    """

    # Empty queryset is what drf-spectacular introspects to derive the
    # response model; the real per-request queryset comes from get_queryset().
    queryset = Plan.objects.none()
    serializer_class = PlanSerializer
    # IsTeamOwnerOrAdmin extends IsAuthenticated and refines two methods
    # only: DELETE and PATCH/PUT-with-visibility. All other actions pass
    # through with just the auth check from the parent class.
    permission_classes = [IsTeamOwnerOrAdmin]
    filterset_fields = ["team", "visibility"]
    # No `search_fields` here — we override get_queryset() to call our
    # FTS .search() method against the GeneratedField tsvector.
    # SearchFilter (icontains) is bypassed in favor of ranked results.
    ordering_fields = ["created_at", "modified_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Plan.objects.for_user(self.request.user).select_related(
            "team", "owner", "created_by"
        )
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            return Plan.objects.for_user(self.request.user).search(search)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class BucketViewSet(viewsets.ModelViewSet):
    """CRUD for Buckets, filtered by `?plan=<id>` for nested-style listing.

    Buckets are conceptually nested under a plan, but we keep them at
    `/api/v1/buckets/` rather than `/api/v1/plans/{id}/buckets/` for two
    reasons: (1) DRF's nested routers are a separate dependency we
    don't need; (2) URL filtering is the same end result with a flat,
    cacheable URL space.

    On create, `position` is auto-assigned to the next slot for the
    target plan — the serializer marks it read-only so clients can't
    pick a position and create gaps/collisions.
    """

    queryset = Bucket.objects.none()
    serializer_class = BucketSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["plan"]
    ordering_fields = ["position", "created_at"]
    ordering = ["position"]

    def get_queryset(self):
        return Bucket.objects.for_user(self.request.user).select_related("plan")

    def perform_create(self, serializer):
        plan = get_object_or_404(
            Plan.objects.for_user(self.request.user),
            pk=serializer.validated_data["plan"].pk,
        )
        position = Bucket.objects.next_position(plan=plan)
        serializer.save(position=position)
