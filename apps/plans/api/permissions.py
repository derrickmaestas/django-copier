"""DRF permission classes for the plans API.

Per-method gates that layer on top of the queryset-level scoping in the
viewsets. The queryset is still the primary defense — non-members get
404 because they can't see the row at all. These classes refine *what
members can do*, not *whether they can see anything at all*.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated

from apps.accounts.models import Membership

# Roles allowed to perform destructive operations on a Plan: deleting it,
# changing its visibility, or transferring ownership. Plain members can
# read and update non-destructive fields but not these.
PRIVILEGED_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN}


class IsTeamOwnerOrAdmin(IsAuthenticated):
    """Member-level gate that escalates for destructive Plan operations.

    Read methods (GET/HEAD/OPTIONS) and most writes (PATCH/PUT) pass
    through with just the IsAuthenticated check from the parent — the
    queryset already filters to plans the user belongs to. Destructive
    operations (DELETE) and visibility changes require the user's
    membership row to be OWNER or ADMIN.

    Why on this class and not in the queryset: the queryset can't
    encode "different verbs allowed for different roles"; that's a
    permission concern, not a visibility concern. We split the two
    concepts so each lives where it's natural.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        if request.method == "DELETE":
            return self._user_has_privileged_role(request.user, obj.team_id)

        if request.method in {"PATCH", "PUT"}:
            # Visibility is the one Plan field that controls who else
            # can find this plan in search and listings — only privileged
            # roles can change it.
            if "visibility" in (request.data or {}):
                return self._user_has_privileged_role(request.user, obj.team_id)

        return True

    @staticmethod
    def _user_has_privileged_role(user, team_id) -> bool:
        return Membership.objects.filter(
            user=user, team_id=team_id, role__in=PRIVILEGED_ROLES,
        ).exists()


class IsTeamMember(BasePermission):
    """Strict membership check — read or write requires a Membership row.

    The queryset already enforces this for list/detail. We expose it as
    a permission class for the few hand-written endpoints that don't
    flow through `for_user()` (e.g. action endpoints that take an
    object id from the URL).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        team_id = getattr(obj, "team_id", None) or getattr(obj.bucket.plan, "team_id", None)
        return Membership.objects.filter(user=request.user, team_id=team_id).exists()
