# domain_launch_assistant/domains/urls.py

from django.urls import path

from domain_launch_assistant.domains.views import (
    DomainResultListView,
    DomainSearchListView,
    DomainSearchStartView,
    DomainSelectView,
)


urlpatterns = [
    path(
        "projects/<uuid:project_id>/domain-search/",
        DomainSearchStartView.as_view(),
        name="domain-search-start",
    ),
    path(
        "projects/<uuid:project_id>/domain-searches/",
        DomainSearchListView.as_view(),
        name="domain-search-list",
    ),
    path(
        "projects/<uuid:project_id>/domains/",
        DomainResultListView.as_view(),
        name="domain-result-list",
    ),
    path(
        "projects/<uuid:project_id>/select-domain/",
        DomainSelectView.as_view(),
        name="domain-select",
    ),
]