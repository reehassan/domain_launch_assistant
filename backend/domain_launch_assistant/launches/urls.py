from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import LaunchProjectViewSet, LaunchReportView

router = DefaultRouter()
router.register("projects", LaunchProjectViewSet, basename="launchproject")

urlpatterns = router.urls + [
    path(
        "projects/<uuid:project_id>/launch-report/",
        LaunchReportView.as_view(),
        name="launch-report",
    ),
]