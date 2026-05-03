from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserSerializer


class MeView(APIView):
    """Return the currently authenticated user.

    Mounted at GET /api/v1/me/. Useful for clients that want to know
    "who am I?" right after logging in — keeps token-based clients
    from having to remember the user they signed in with.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)
