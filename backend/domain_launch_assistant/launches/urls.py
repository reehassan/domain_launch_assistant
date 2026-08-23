from rest_framework.routers import DefaultRouter
from .views import LaunchProjectViewSet

router = DefaultRouter()
router.register("projects", LaunchProjectViewSet, basename="launchproject")
urlpatterns = router.urls