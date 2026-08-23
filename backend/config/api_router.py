from django.urls import path, include

urlpatterns = [
    path("auth/", include("domain_launch_assistant.accounts.urls")),
    path("", include("domain_launch_assistant.launches.urls")),
]