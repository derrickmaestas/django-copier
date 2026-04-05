# REST APIs with Django REST Framework

## Project Structure

Keep API code in `api/` subpackages within each app — separate from server-rendered views:

```
apps/tasks/
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── permissions.py
│   └── filters.py
├── models.py
├── views.py            # server-rendered views (coexist)
└── forms.py
```

## Settings

```python
# config/settings/base.py
INSTALLED_APPS = [
    # ...
    "rest_framework",
    "django_filters",
    "drf_spectacular",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%SZ",
    "DATE_FORMAT": "%Y-%m-%d",
}

# JWT
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# OpenAPI docs
SPECTACULAR_SETTINGS = {
    "TITLE": "Planly API",
    "DESCRIPTION": "Task management API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}
```

## Serializers

**Never use `fields = "__all__"`** — explicitly list fields to avoid accidental exposure. Use separate serializers for list, detail, and create/update:

```python
# apps/tasks/api/serializers.py
from rest_framework import serializers
from tasks.models import Task


class TaskListSerializer(serializers.ModelSerializer):
    """Lightweight — for board/list views."""
    assignee_count = serializers.IntegerField(source="assignments.count", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = ["id", "title", "priority", "progress", "due_date",
                  "assignee_count", "is_overdue", "bucket"]


class TaskDetailSerializer(serializers.ModelSerializer):
    """Full — includes nested relations."""
    assignees = UserSummarySerializer(many=True, read_only=True)
    labels = LabelSerializer(many=True, read_only=True)
    checklist_items = ChecklistItemSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = ["id", "title", "description", "priority", "progress",
                  "start_date", "due_date", "completed_at", "bucket",
                  "created_by", "assignees", "labels", "checklist_items",
                  "comments", "created_at", "modified_at"]
        read_only_fields = ["id", "created_by", "completed_at", "created_at", "modified_at"]


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    """Write — accepts IDs for relations."""
    label_ids = serializers.PrimaryKeyRelatedField(
        queryset=Label.objects.all(), many=True, required=False, source="labels",
    )

    class Meta:
        model = Task
        fields = ["title", "description", "bucket", "priority",
                  "start_date", "due_date", "label_ids", "recurrence_rule"]

    def validate(self, data):
        start = data.get("start_date")
        due = data.get("due_date")
        if start and due and start > due:
            raise serializers.ValidationError(
                {"due_date": "Due date must be on or after start date."}
            )
        return data
```

## ViewSets

| Class | Use when |
|---|---|
| `ModelViewSet` | Standard CRUD | 
| `mixins` + `GenericViewSet` | Only some CRUD actions |
| `APIView` | Non-CRUD, custom logic |
| `@action` decorator | Extra endpoint on existing ViewSet |

**Scope querysets to the current user** in `get_queryset()` — this is the primary access control:

```python
class TaskViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsTeamMember]
    filterset_class = TaskFilter
    search_fields = ["title", "description"]
    ordering_fields = ["priority", "due_date", "created_at"]

    def get_queryset(self):
        return (
            Task.objects
            .filter(bucket__plan__team__memberships__user=self.request.user)
            .select_related("bucket__plan")
            .prefetch_related("assignees", "labels", "checklist_items")
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "list":
            return TaskListSerializer
        if self.action in ("create", "update", "partial_update"):
            return TaskCreateUpdateSerializer
        return TaskDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.mark_complete()
        return Response(TaskDetailSerializer(task).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        task = self.get_object()
        user_ids = request.data.get("user_ids", [])
        users = User.objects.filter(pk__in=user_ids)
        for user in users:
            Assignment.objects.get_or_create(
                task=task, user=user,
                defaults={"assigned_by": request.user},
            )
        return Response(TaskDetailSerializer(task).data)
```

## Permissions

```python
# apps/tasks/api/permissions.py
class IsTeamMember(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "bucket"):
            plan = obj.bucket.plan
        elif hasattr(obj, "plan"):
            plan = obj.plan
        elif hasattr(obj, "team"):
            plan = obj
        else:
            return False
        team = plan.team if hasattr(plan, "team") else plan
        return team.memberships.filter(user=request.user).exists()
```

## Filtering

```python
# apps/tasks/api/filters.py
import django_filters
from tasks.models import Task


class TaskFilter(django_filters.FilterSet):
    bucket = django_filters.NumberFilter(field_name="bucket_id")
    plan = django_filters.NumberFilter(field_name="bucket__plan_id")
    assignee = django_filters.NumberFilter(field_name="assignments__user_id")
    priority = django_filters.ChoiceFilter(choices=Task.Priority.choices)
    overdue = django_filters.BooleanFilter(method="filter_overdue")
    due_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    due_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")

    class Meta:
        model = Task
        fields = ["bucket", "plan", "assignee", "priority", "progress"]

    def filter_overdue(self, queryset, name, value):
        if value:
            return queryset.overdue()
        return queryset
```

## URL Routing

Versioned at `/api/v1/` with `DefaultRouter`:

```python
# apps/tasks/api/urls.py
from rest_framework.routers import DefaultRouter
from tasks.api import views

router = DefaultRouter()
router.register(r"tasks", views.TaskViewSet, basename="task")
router.register(r"comments", views.CommentViewSet, basename="comment")

urlpatterns = router.urls
```

```python
# config/urls.py
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Server-rendered views
    path("plans/", include("plans.urls", namespace="plans")),
    path("tasks/", include("tasks.urls", namespace="tasks")),
    # ...

    # API v1
    path("api/v1/", include("plans.api.urls")),
    path("api/v1/", include("tasks.api.urls")),
    path("api/v1/auth/", include("rest_framework_simplejwt.urls")),

    # API docs
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
]
```

## CORS

```python
# config/settings/production.py
INSTALLED_APPS += ["corsheaders"]
MIDDLEWARE.insert(0, "corsheaders.middleware.CorsMiddleware")

CORS_ALLOWED_ORIGINS = [
    "https://app.planly.example.com",
]
CORS_ALLOW_CREDENTIALS = True
```

Never use `CORS_ALLOW_ALL_ORIGINS` in production.

## Customizing OpenAPI Docs with `@extend_schema`

When auto-generated schema isn't accurate enough, use `@extend_schema`:

```python
from drf_spectacular.utils import extend_schema, OpenApiExample


class TaskViewSet(viewsets.ModelViewSet):
    @extend_schema(
        summary="Mark task complete",
        description="Sets progress to 100% and records the completion timestamp.",
        responses={200: TaskDetailSerializer},
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.mark_complete()
        return Response(TaskDetailSerializer(task).data)

    @extend_schema(
        summary="Assign users to task",
        request={"application/json": {"type": "object", "properties": {
            "user_ids": {"type": "array", "items": {"type": "integer"}},
        }}},
        responses={200: TaskDetailSerializer},
        examples=[
            OpenApiExample(
                "Assign two users",
                value={"user_ids": [1, 2]},
                request_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        ...
```

## Error Response Format

DRF returns structured errors by default. Keep this format consistent:

```json
// Field-level validation errors
{
    "title": ["This field may not be blank."],
    "due_date": ["Due date must be on or after start date."]
}

// Non-field errors
{
    "detail": "You do not have permission to perform this action."
}
```

## Schema Validation in CI

```bash
python manage.py spectacular --validate --fail-on-warn
```

## Testing API Endpoints

Use DRF's `APIClient`:

```python
@pytest.mark.django_db
class TestTaskAPI:
    def setup_method(self):
        self.client = APIClient()
        self.membership = MembershipFactory()
        self.user = self.membership.user
        self.client.force_authenticate(user=self.user)

    def test_list_tasks(self):
        bucket = BucketFactory(plan=self.plan)
        TaskFactory.create_batch(3, bucket=bucket)
        response = self.client.get("/api/v1/tasks/", {"plan": self.plan.pk})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_non_member_cannot_access(self):
        outsider = UserFactory()
        self.client.force_authenticate(user=outsider)
        response = self.client.get("/api/v1/tasks/")
        assert response.data["count"] == 0
```
