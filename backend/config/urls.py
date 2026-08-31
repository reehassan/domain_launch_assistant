from django.contrib import admin
from django.urls import path, include

from config.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("api/v1/", include("config.api_router")),
]