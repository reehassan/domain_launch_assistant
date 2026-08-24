from django.urls import path

from domain_launch_assistant.brands.views import (
    BrandGenerateView,
    BrandIdeaListView,
    BrandIdeaSelectView,
)


urlpatterns = [
    path(
        "projects/<uuid:project_id>/generate-brands/",
        BrandGenerateView.as_view(),
        name="brand-generate",
    ),
    path(
        "projects/<uuid:project_id>/brands/",
        BrandIdeaListView.as_view(),
        name="brand-list",
    ),
    path(
        "projects/<uuid:project_id>/select-brand/",
        BrandIdeaSelectView.as_view(),
        name="brand-select",
    ),
]
