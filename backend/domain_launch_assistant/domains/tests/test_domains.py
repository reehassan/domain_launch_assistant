# domain_launch_assistant/domains/tests/test_domains.py

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComTimeoutError,
)
from domain_launch_assistant.domains.models import DomainResult, DomainSearch
from domain_launch_assistant.launches.models import LaunchProject

pytestmark = pytest.mark.django_db


def _mock_namecom():
    """
    Patches NameComClient at the point availability.py imports it, so
    AvailabilityService() picks up the mock without any code changes —
    same pattern as _mock_gemini() in test_brands.py.
    """
    return patch(
        "domain_launch_assistant.domains.services.availability.NameComClient"
    )


def _raw_result(domain: str, purchasable: bool):
    return {"domainName": domain, "purchasable": purchasable}


def _create_domain_result(project, search, domain="ledgerflow.ai", available=True):
    return DomainResult.objects.create(
        search=search,
        project=project,
        domain=domain,
        extension=domain[domain.rindex("."):],
        available=available,
        status=DomainResult.Status.AVAILABLE if available else DomainResult.Status.TAKEN,
        provider="name.com",
        checked_at=timezone.now(),
    )


def _create_search(project, brand_idea, status_=DomainSearch.Status.COMPLETED):
    return DomainSearch.objects.create(
        project=project,
        brand_idea=brand_idea,
        status=status_,
        requested_extensions=[".com", ".ai"],
    )


class TestStartDomainSearch:
    def test_start_search_success(self, auth_client_a, project_a, brand_idea_a):
        with _mock_namecom() as MockClient:
            instance = MockClient.return_value
            instance.check_availability.return_value = [
                _raw_result("ledgerflow.com", purchasable=False),
                _raw_result("ledgerflow.ai", purchasable=True),
            ]
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/domain-search/",
                {"brand_idea_id": str(brand_idea_a.id), "extensions": [".com", ".ai"]},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["project_id"] == str(project_a.id)
        assert response.data["status"] == DomainSearch.Status.COMPLETED
        assert "search_id" in response.data
        assert "task_id" in response.data

        search = DomainSearch.objects.get(id=response.data["search_id"])
        results = DomainResult.objects.filter(search=search)
        assert results.count() == 2
        taken = results.get(domain="ledgerflow.com")
        available = results.get(domain="ledgerflow.ai")
        assert taken.status == DomainResult.Status.TAKEN
        assert taken.available is False
        assert available.status == DomainResult.Status.AVAILABLE
        assert available.available is True

    def test_start_search_missing_brand_idea_id(self, auth_client_a, project_a):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/domain-search/",
            {"extensions": [".com"]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_start_search_invalid_extension(self, auth_client_a, project_a, brand_idea_a):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/domain-search/",
            {"brand_idea_id": str(brand_idea_a.id), "extensions": [".zzz"]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_start_search_brand_idea_from_other_project_fails(
        self, auth_client_a, project_a, brand_idea_b
    ):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/domain-search/",
            {"brand_idea_id": str(brand_idea_b.id), "extensions": [".com"]},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_start_search_other_users_project(self, auth_client_a, project_b, brand_idea_b):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_b.id}/domain-search/",
            {"brand_idea_id": str(brand_idea_b.id), "extensions": [".com"]},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_start_search_unauthenticated(self, project_a, brand_idea_a):
        client = APIClient()
        response = client.post(
            f"/api/v1/projects/{project_a.id}/domain-search/",
            {"brand_idea_id": str(brand_idea_a.id), "extensions": [".com"]},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_start_search_provider_timeout_returns_502(
        self, auth_client_a, project_a, brand_idea_a
    ):
        with _mock_namecom() as MockClient:
            instance = MockClient.return_value
            instance.check_availability.side_effect = NameComTimeoutError("timed out")
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/domain-search/",
                {"brand_idea_id": str(brand_idea_a.id), "extensions": [".com"]},
                format="json",
            )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert response.data["error"]["code"] == "EXTERNAL_API_TIMEOUT"

        search = DomainSearch.objects.get(project=project_a)
        assert search.status == DomainSearch.Status.FAILED
        assert search.error_message == "timed out"
        assert DomainResult.objects.filter(search=search).count() == 0

    def test_start_search_provider_error_returns_503(
        self, auth_client_a, project_a, brand_idea_a
    ):
        with _mock_namecom() as MockClient:
            instance = MockClient.return_value
            instance.check_availability.side_effect = NameComAPIError("server error")
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/domain-search/",
                {"brand_idea_id": str(brand_idea_a.id), "extensions": [".com"]},
                format="json",
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["error"]["code"] == "EXTERNAL_API_ERROR"

        search = DomainSearch.objects.get(project=project_a)
        assert search.status == DomainSearch.Status.FAILED

    def test_start_search_unslugifiable_brand_name_returns_400(
        self, auth_client_a, project_a
    ):
        """
        Regression test: a brand name with no valid domain-label
        characters (all punctuation) must fail cleanly as
        VALIDATION_ERROR, not crash or silently produce an empty domain.
        """
        from domain_launch_assistant.brands.models import BrandIdea

        odd_brand = BrandIdea.objects.create(
            project=project_a, name="???", description="d"
        )
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/domain-search/",
            {"brand_idea_id": str(odd_brand.id), "extensions": [".com"]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_start_search_provider_omits_a_domain_marks_check_failed(
        self, auth_client_a, project_a, brand_idea_a
    ):
        """
        Regression test: if name.com's response is missing one of the
        requested domains (the overall call succeeded), that domain
        must be recorded as CHECK_FAILED, not silently dropped or
        interpreted as TAKEN.
        """
        with _mock_namecom() as MockClient:
            instance = MockClient.return_value
            instance.check_availability.return_value = [
                _raw_result("ledgerflow.com", purchasable=True),
                # .ai deliberately missing from the response
            ]
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/domain-search/",
                {"brand_idea_id": str(brand_idea_a.id), "extensions": [".com", ".ai"]},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        search = DomainSearch.objects.get(id=response.data["search_id"])
        missing = DomainResult.objects.get(search=search, domain="ledgerflow.ai")
        assert missing.status == DomainResult.Status.CHECK_FAILED
        assert missing.available is False


class TestListDomainSearches:
    def test_list_returns_only_this_projects_searches(
        self, auth_client_a, project_a, project_b, brand_idea_a, brand_idea_b
    ):
        _create_search(project_a, brand_idea_a)
        _create_search(project_b, brand_idea_b)

        response = auth_client_a.get(f"/api/v1/projects/{project_a.id}/domain-searches/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_list_other_users_project(self, auth_client_a, project_b):
        response = auth_client_a.get(f"/api/v1/projects/{project_b.id}/domain-searches/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_unauthenticated(self, project_a):
        client = APIClient()
        response = client.get(f"/api/v1/projects/{project_a.id}/domain-searches/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestListDomainResults:
    def test_list_returns_only_this_projects_results(
        self, auth_client_a, project_a, project_b, brand_idea_a, brand_idea_b
    ):
        search_a = _create_search(project_a, brand_idea_a)
        search_b = _create_search(project_b, brand_idea_b)
        _create_domain_result(project_a, search_a, domain="mine.com")
        _create_domain_result(project_b, search_b, domain="notmine.com")

        response = auth_client_a.get(f"/api/v1/projects/{project_a.id}/domains/")

        assert response.status_code == status.HTTP_200_OK
        domains = [r["domain"] for r in response.data["results"]]
        assert domains == ["mine.com"]

    def test_filter_by_available(self, auth_client_a, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        _create_domain_result(project_a, search, domain="taken.com", available=False)
        _create_domain_result(project_a, search, domain="free.ai", available=True)

        response = auth_client_a.get(
            f"/api/v1/projects/{project_a.id}/domains/?available=true"
        )

        assert response.status_code == status.HTTP_200_OK
        domains = [r["domain"] for r in response.data["results"]]
        assert domains == ["free.ai"]

    def test_filter_by_extension(self, auth_client_a, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        _create_domain_result(project_a, search, domain="mine.com")
        _create_domain_result(project_a, search, domain="mine.ai")

        response = auth_client_a.get(
            f"/api/v1/projects/{project_a.id}/domains/?extension=.ai"
        )

        assert response.status_code == status.HTTP_200_OK
        domains = [r["domain"] for r in response.data["results"]]
        assert domains == ["mine.ai"]

    def test_filter_by_search_term(self, auth_client_a, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        _create_domain_result(project_a, search, domain="ledgerflow.com")
        _create_domain_result(project_a, search, domain="finora.com")

        response = auth_client_a.get(
            f"/api/v1/projects/{project_a.id}/domains/?search=ledger"
        )

        assert response.status_code == status.HTTP_200_OK
        domains = [r["domain"] for r in response.data["results"]]
        assert domains == ["ledgerflow.com"]

    def test_list_other_users_project(self, auth_client_a, project_b):
        response = auth_client_a.get(f"/api/v1/projects/{project_b.id}/domains/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_unauthenticated(self, project_a):
        client = APIClient()
        response = client.get(f"/api/v1/projects/{project_a.id}/domains/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestSelectDomain:
    def test_select_domain_success(self, auth_client_a, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)

        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/select-domain/",
            {"domain_id": str(result.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == LaunchProject.Status.DOMAIN_SELECTED
        assert response.data["selected_domain"]["id"] == str(result.id)

        project_a.refresh_from_db()
        assert project_a.selected_domain_id == result.id
        assert project_a.status == LaunchProject.Status.DOMAIN_SELECTED

    def test_select_domain_missing_domain_id(self, auth_client_a, project_a):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/select-domain/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_select_domain_not_available_fails(self, auth_client_a, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="taken.com", available=False)

        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/select-domain/",
            {"domain_id": str(result.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "CONFLICT"
        project_a.refresh_from_db()
        assert project_a.selected_domain_id is None

    def test_select_domain_stale_availability_fails(
        self, auth_client_a, project_a, brand_idea_a, settings
    ):
        settings.DOMAIN_FRESHNESS_THRESHOLD_SECONDS = 300
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)
        result.checked_at = timezone.now() - timedelta(seconds=600)
        result.save(update_fields=["checked_at"])

        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/select-domain/",
            {"domain_id": str(result.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "CONFLICT"

    def test_select_domain_belonging_to_other_project_fails(
        self, auth_client_a, project_a, project_b, brand_idea_b
    ):
        search = _create_search(project_b, brand_idea_b)
        foreign_result = _create_domain_result(project_b, search, domain="notyours.com")

        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/select-domain/",
            {"domain_id": str(foreign_result.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_select_domain_other_users_project(self, auth_client_a, project_b, brand_idea_b):
        search = _create_search(project_b, brand_idea_b)
        result = _create_domain_result(project_b, search, domain="theirs.com")

        response = auth_client_a.post(
            f"/api/v1/projects/{project_b.id}/select-domain/",
            {"domain_id": str(result.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_select_domain_unauthenticated(self, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="ledgerflow.ai")
        client = APIClient()
        response = client.post(
            f"/api/v1/projects/{project_a.id}/select-domain/",
            {"domain_id": str(result.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED