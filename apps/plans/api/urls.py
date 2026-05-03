from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BucketViewSet, PlanViewSet

router = DefaultRouter()
router.register("plans", PlanViewSet, basename="plan")
router.register("buckets", BucketViewSet, basename="bucket")

urlpatterns = [
    path("", include(router.urls)),
]
