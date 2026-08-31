# config/api_router.py

from django.urls import include, path

urlpatterns = [
    path(
        "auth/",
        include("domain_launch_assistant.accounts.urls"),
    ),
    path(
        "",
        include("domain_launch_assistant.launches.urls"),
    ),
    path(
        "",
        include("domain_launch_assistant.brands.urls"),
    ),
    path(
        "",
        include("domain_launch_assistant.domains.urls"),
    ),
    path(
        "",
        include("domain_launch_assistant.dns.urls"),
    ),
    path(
        "",
        include("domain_launch_assistant.tasks.urls"),
    ),
]