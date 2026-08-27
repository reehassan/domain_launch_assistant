# domain_launch_assistant/domains/urls.py

from django.urls import path

from domain_launch_assistant.domains.views import (
    DomainClaimListView,
    DomainClaimsCheckView,
    DomainRecommendGenerateView,
    DomainRecommendationListView,
    DomainRegistrationSimulateView,
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
    path(
        "projects/<uuid:project_id>/recommend-domain/",
        DomainRecommendGenerateView.as_view(),
        name="domain-recommend-generate",
    ),
    path(
        "projects/<uuid:project_id>/domain-recommendations/",
        DomainRecommendationListView.as_view(),
        name="domain-recommendation-list",
    ),
    path(
        "domains/<uuid:domain_id>/check-claims/",
        DomainClaimsCheckView.as_view(),
        name="domain-claims-check",
    ),
    path(
        "domains/<uuid:domain_id>/claims/",
        DomainClaimListView.as_view(),
        name="domain-claims-list",
    ),
    path(
        "domains/<uuid:domain_id>/simulate-registration/",
        DomainRegistrationSimulateView.as_view(),
        name="domain-registration-simulate",
    ),
]