# domain_launch_assistant/domains/tests/conftest.py

import pytest

from domain_launch_assistant.brands.models import BrandIdea

# Shared fixtures (user_a, user_b, auth_client_a, auth_client_b,
# project_a, project_b) live in the root conftest.py.


@pytest.fixture
def brand_idea_a(project_a):
    return BrandIdea.objects.create(
        project=project_a,
        name="LedgerFlow",
        description="Suggests financial clarity and continuous workflow.",
    )


@pytest.fixture
def brand_idea_b(project_b):
    return BrandIdea.objects.create(
        project=project_b,
        name="Someone Else's Brand",
        description="d",
    )