# domain_launch_assistant/dns/tests/conftest.py

import pytest
from django.utils import timezone

from domain_launch_assistant.brands.models import BrandIdea
from domain_launch_assistant.domains.models import DomainResult, DomainSearch

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


@pytest.fixture
def domain_search_a(project_a, brand_idea_a):
    return DomainSearch.objects.create(
        project=project_a,
        brand_idea=brand_idea_a,
        status=DomainSearch.Status.COMPLETED,
        requested_extensions=[".ai"],
    )


@pytest.fixture
def domain_search_b(project_b, brand_idea_b):
    return DomainSearch.objects.create(
        project=project_b,
        brand_idea=brand_idea_b,
        status=DomainSearch.Status.COMPLETED,
        requested_extensions=[".com"],
    )


@pytest.fixture
def domain_result_a(project_a, domain_search_a):
    """
    An AVAILABLE domain result on project_a, not yet selected onto it.
    Individual tests select it where that matters (e.g. DOMAIN_READINESS
    PASS requires it to actually be the project's selected domain).
    """
    return DomainResult.objects.create(
        search=domain_search_a,
        project=project_a,
        domain="ledgerflow.ai",
        extension=".ai",
        available=True,
        status=DomainResult.Status.AVAILABLE,
        provider="name.com",
        checked_at=timezone.now(),
    )


@pytest.fixture
def domain_result_b(project_b, domain_search_b):
    return DomainResult.objects.create(
        search=domain_search_b,
        project=project_b,
        domain="theirs.com",
        extension=".com",
        available=True,
        status=DomainResult.Status.AVAILABLE,
        provider="name.com",
        checked_at=timezone.now(),
    )