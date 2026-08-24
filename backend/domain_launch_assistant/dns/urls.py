# domain_launch_assistant/dns/urls.py

from django.urls import path

from domain_launch_assistant.dns.views import (
    CheckDomainView,
    DomainCheckListView,
)


urlpatterns = [
    path(
        "domains/<uuid:domain_id>/check/",
        CheckDomainView.as_view(),
        name="domain-check-start",
    ),
    path(
        "domains/<uuid:domain_id>/checks/",
        DomainCheckListView.as_view(),
        name="domain-check-list",
    ),
]