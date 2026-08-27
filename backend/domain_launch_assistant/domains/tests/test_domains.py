# domain_launch_assistant/domains/tests/test_domains.py

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from domain_launch_assistant.core.integrations.gemini.client import GeminiClientError
from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComTimeoutError,
)

from domain_launch_assistant.domains.clients.namecom import NameComClient
from domain_launch_assistant.domains.models import (
    DomainClaim,
    DomainRecommendation,
    DomainResult,
    DomainSearch,
)
from domain_launch_assistant.domains.services.registration_simulation import (
    DomainRegistrationSimulationGuardError,
    DomainRegistrationSimulationService,
)
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.tasks.models import TaskRecord

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


def _mock_namecom_claims():
    """
    Patches NameComClient at the point domain_claims.py imports it, so
    DomainClaimsService() picks up the mock without any code changes —
    same pattern as _mock_namecom() above (which patches it for
    availability.py's AvailabilityService instead).
    """
    return patch(
        "domain_launch_assistant.domains.services.domain_claims.NameComClient"
    )


def _mock_registration_namecom():
    """
    Patches NameComClient at the point registration_simulation.py imports
    it, so DomainRegistrationSimulationService() picks up the mock
    without any code changes — same pattern as _mock_namecom() /
    _mock_namecom_claims() above.
    """
    return patch(
        "domain_launch_assistant.domains.services.registration_simulation.NameComClient"
    )


def _mock_gemini_recommendation():
    """
    Patches GeminiClient at the point domain_recommendation.py imports
    it, so DomainRecommendationService() picks up the mock without any
    code changes — same pattern as _mock_gemini() in test_brands.py.
    """
    return patch(
        "domain_launch_assistant.core.services.domain_recommendation.GeminiClient"
    )


def _raw_result(
    domain: str,
    purchasable: bool,
    premium: bool | None = None,
    purchase_price: float | None = None,
    renewal_price: float | None = None,
    purchase_type: str | None = None,
):
    raw = {"domainName": domain, "purchasable": purchasable}
    if premium is not None:
        raw["premium"] = premium
    if purchase_price is not None:
        raw["purchasePrice"] = purchase_price
    if renewal_price is not None:
        raw["renewalPrice"] = renewal_price
    if purchase_type is not None:
        raw["purchaseType"] = purchase_type
    return raw


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


def _create_domain_recommendation(
    project,
    recommended_domain,
    reasoning="Strong brand alignment and a short, memorable domain.",
):
    return DomainRecommendation.objects.create(
        project=project,
        recommended_domain=recommended_domain,
        reasoning=reasoning,
    )


def _create_domain_claim(domain_result, has_claims=False, claims_data=None, checked_at=None):
    return DomainClaim.objects.create(
        domain_result=domain_result,
        has_claims=has_claims,
        claims_data=claims_data if claims_data is not None else {"claims": [], "claimId": None},
        checked_at=checked_at or timezone.now(),
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
        assert response.data["status"] == "PROCESSING"
        assert "search_id" in response.data
        assert "task_id" in response.data

        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS

        search = DomainSearch.objects.get(id=response.data["search_id"])
        assert search.status == DomainSearch.Status.COMPLETED
        results = DomainResult.objects.filter(search=search)
        assert results.count() == 2
        taken = results.get(domain="ledgerflow.com")
        available = results.get(domain="ledgerflow.ai")
        assert taken.status == DomainResult.Status.TAKEN
        assert taken.available is False
        assert available.status == DomainResult.Status.AVAILABLE
        assert available.available is True

    def test_start_search_persists_pricing_fields(
        self, auth_client_a, project_a, brand_idea_a
    ):
        with _mock_namecom() as MockClient:
            instance = MockClient.return_value
            instance.check_availability.return_value = [
                _raw_result(
                    "ledgerflow.ai",
                    purchasable=True,
                    premium=True,
                    purchase_price=69.99,
                    renewal_price=69.99,
                ),
            ]
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/domain-search/",
                {"brand_idea_id": str(brand_idea_a.id), "extensions": [".ai"]},
                format="json",
            )
        assert response.status_code == status.HTTP_202_ACCEPTED
        result = DomainResult.objects.get(domain="ledgerflow.ai")
        assert result.purchase_price == Decimal("69.99")
        assert result.renewal_price == Decimal("69.99")
        assert result.premium is True
        # purchaseType absent from the mocked raw response -> defaults
        # to "registration" for an available result, per name.com's
        # own stated recommendation (see availability.py comment).
        assert result.purchase_type == "registration"

    def test_start_search_taken_domain_has_no_pricing(
        self, auth_client_a, project_a, brand_idea_a
    ):
        with _mock_namecom() as MockClient:
            instance = MockClient.return_value
            instance.check_availability.return_value = [
                _raw_result("ledgerflow.com", purchasable=False),
            ]
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/domain-search/",
                {"brand_idea_id": str(brand_idea_a.id), "extensions": [".com"]},
                format="json",
            )
        assert response.status_code == status.HTTP_202_ACCEPTED
        result = DomainResult.objects.get(domain="ledgerflow.com")
        assert result.purchase_price is None
        assert result.renewal_price is None
        assert result.purchase_type is None

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

    def test_start_search_provider_timeout_marks_task_failed(
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

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "EXTERNAL_API_TIMEOUT"

        search = DomainSearch.objects.get(project=project_a)
        assert search.status == DomainSearch.Status.FAILED
        assert search.error_message == "timed out"
        assert DomainResult.objects.filter(search=search).count() == 0

    def test_start_search_provider_error_marks_task_failed(
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

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "EXTERNAL_API_ERROR"

        search = DomainSearch.objects.get(project=project_a)
        assert search.status == DomainSearch.Status.FAILED

    def test_start_search_unslugifiable_brand_name_marks_task_failed(
        self, auth_client_a, project_a
    ):
        from domain_launch_assistant.brands.models import BrandIdea

        odd_brand = BrandIdea.objects.create(
            project=project_a, name="???", description="d"
        )
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/domain-search/",
            {"brand_idea_id": str(odd_brand.id), "extensions": [".com"]},
            format="json",
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "VALIDATION_ERROR"

    def test_start_search_provider_omits_a_domain_marks_check_failed(
        self, auth_client_a, project_a, brand_idea_a
    ):
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

    def test_list_includes_pricing_fields_in_response(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )
        result.purchase_price = 69.99
        result.renewal_price = 69.99
        result.premium = False
        result.purchase_type = "registration"
        result.save(
            update_fields=[
                "purchase_price",
                "renewal_price",
                "premium",
                "purchase_type",
            ]
        )
        response = auth_client_a.get(f"/api/v1/projects/{project_a.id}/domains/")
        assert response.status_code == status.HTTP_200_OK
        row = response.data["results"][0]
        assert row["purchase_price"] == "69.99"
        assert row["renewal_price"] == "69.99"
        assert row["premium"] is False
        assert row["purchase_type"] == "registration"

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


class TestRecommendDomain:
    def test_recommend_domain_success(self, auth_client_a, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        available = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )

        with _mock_gemini_recommendation() as MockClient:
            instance = MockClient.return_value
            instance.recommend_domain.return_value = {
                "recommended_domain_id": str(available.id),
                "reasoning": "Short, brandable, and matches the .ai positioning.",
            }
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/recommend-domain/",
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["status"] == "PROCESSING"

        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS

        recommendation = DomainRecommendation.objects.get(project=project_a)
        assert recommendation.recommended_domain_id == available.id
        assert (
            recommendation.reasoning
            == "Short, brandable, and matches the .ai positioning."
        )

    def test_recommend_domain_no_domain_search_yet_returns_409(
        self, auth_client_a, project_a
    ):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/recommend-domain/",
            format="json",
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "CONFLICT"

    def test_recommend_domain_no_available_domains_returns_400(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        _create_domain_result(project_a, search, domain="ledgerflow.com", available=False)

        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/recommend-domain/",
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_recommend_domain_hallucinated_id_marks_task_failed(
        self, auth_client_a, project_a, brand_idea_a
    ):
        """
        Gemini referencing a domain_id that isn't one of the project's
        AVAILABLE results must never be persisted, regardless of how
        plausible the reasoning text looks.
        """
        search = _create_search(project_a, brand_idea_a)
        _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)

        with _mock_gemini_recommendation() as MockClient:
            instance = MockClient.return_value
            instance.recommend_domain.return_value = {
                "recommended_domain_id": "00000000-0000-0000-0000-000000000000",
                "reasoning": "A domain that does not exist in this project.",
            }
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/recommend-domain/",
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "AI_GENERATION_FAILED"
        assert DomainRecommendation.objects.filter(project=project_a).count() == 0

    def test_recommend_domain_empty_reasoning_marks_task_failed(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        available = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )

        with _mock_gemini_recommendation() as MockClient:
            instance = MockClient.return_value
            instance.recommend_domain.return_value = {
                "recommended_domain_id": str(available.id),
                "reasoning": "   ",
            }
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/recommend-domain/",
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "AI_GENERATION_FAILED"
        assert DomainRecommendation.objects.filter(project=project_a).count() == 0

    def test_recommend_domain_gemini_client_error_marks_task_failed(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)

        with _mock_gemini_recommendation() as MockClient:
            instance = MockClient.return_value
            instance.recommend_domain.side_effect = GeminiClientError("boom")
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/recommend-domain/",
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "AI_GENERATION_FAILED"
        assert DomainRecommendation.objects.filter(project=project_a).count() == 0

    def test_recommend_domain_other_users_project(self, auth_client_a, project_b):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_b.id}/recommend-domain/",
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_recommend_domain_unauthenticated(self, project_a):
        client = APIClient()
        response = client.post(
            f"/api/v1/projects/{project_a.id}/recommend-domain/",
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestListDomainRecommendations:
    def test_list_returns_only_this_projects_recommendations(
        self, auth_client_a, project_a, project_b, brand_idea_a, brand_idea_b
    ):
        search_a = _create_search(project_a, brand_idea_a)
        search_b = _create_search(project_b, brand_idea_b)
        available_a = _create_domain_result(
            project_a, search_a, domain="mine.ai", available=True
        )
        available_b = _create_domain_result(
            project_b, search_b, domain="notmine.ai", available=True
        )
        _create_domain_recommendation(project_a, available_a)
        _create_domain_recommendation(project_b, available_b)

        response = auth_client_a.get(
            f"/api/v1/projects/{project_a.id}/domain-recommendations/"
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["recommended_domain"]["domain"] == "mine.ai"

    def test_list_orders_newest_first(self, auth_client_a, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        available = _create_domain_result(
            project_a, search, domain="mine.ai", available=True
        )
        older = _create_domain_recommendation(
            project_a, available, reasoning="First pick."
        )
        newer = _create_domain_recommendation(
            project_a, available, reasoning="Regenerated pick."
        )
        DomainRecommendation.objects.filter(id=older.id).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )

        response = auth_client_a.get(
            f"/api/v1/projects/{project_a.id}/domain-recommendations/"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0]["id"] == str(newer.id)

    def test_list_other_users_project(self, auth_client_a, project_b):
        response = auth_client_a.get(
            f"/api/v1/projects/{project_b.id}/domain-recommendations/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_unauthenticated(self, project_a):
        client = APIClient()
        response = client.get(
            f"/api/v1/projects/{project_a.id}/domain-recommendations/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCheckDomainClaims:
    def test_check_claims_success_no_claims(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )

        with _mock_namecom_claims() as MockClient:
            instance = MockClient.return_value
            instance.get_domain_claims.return_value = {
                "domain": "ledgerflow.ai",
                "claims": [],
                "claimsProcessActive": False,
                "claimId": None,
                "notBefore": None,
                "notAfter": None,
                "claimsNotice": "",
            }
            response = auth_client_a.post(
                f"/api/v1/domains/{result.id}/check-claims/",
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["domain_id"] == str(result.id)

        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS

        claim = DomainClaim.objects.get(domain_result=result)
        assert claim.has_claims is False

    def test_check_claims_success_has_claims(
        self, auth_client_a, project_a, brand_idea_a
    ):
        """
        Per name.com's documented response shape, `claims` can be an
        empty list even when a claim exists — the authoritative "has a
        claim" signal is the top-level claimId being non-null, not
        list length. See docs.name.com's Check Domain Claims reference.
        """
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(
            project_a, search, domain="tiktok.page", available=True
        )

        with _mock_namecom_claims() as MockClient:
            instance = MockClient.return_value
            instance.get_domain_claims.return_value = {
                "domain": "tiktok.page",
                "claims": [],
                "claimsProcessActive": True,
                "claimId": "8c3027d30000000000382500785",
                "notBefore": "2020-01-01T00:00:00Z",
                "notAfter": "2030-01-01T00:00:00Z",
                "claimsNotice": "This domain may infringe on a trademark claim.",
            }
            response = auth_client_a.post(
                f"/api/v1/domains/{result.id}/check-claims/",
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS

        claim = DomainClaim.objects.get(domain_result=result)
        assert claim.has_claims is True
        assert claim.claims_data["claimId"] == "8c3027d30000000000382500785"

    def test_check_claims_provider_timeout_persists_nothing(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )

        with _mock_namecom_claims() as MockClient:
            instance = MockClient.return_value
            instance.get_domain_claims.side_effect = NameComTimeoutError("timed out")
            response = auth_client_a.post(
                f"/api/v1/domains/{result.id}/check-claims/",
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "EXTERNAL_API_TIMEOUT"
        # Critical invariant: a provider timeout must never be
        # persisted or misread as "no claims".
        assert DomainClaim.objects.filter(domain_result=result).count() == 0

    def test_check_claims_provider_error_persists_nothing(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )

        with _mock_namecom_claims() as MockClient:
            instance = MockClient.return_value
            instance.get_domain_claims.side_effect = NameComAPIError("server error")
            response = auth_client_a.post(
                f"/api/v1/domains/{result.id}/check-claims/",
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "EXTERNAL_API_ERROR"
        assert DomainClaim.objects.filter(domain_result=result).count() == 0

    def test_check_claims_other_users_domain_fails(
        self, auth_client_a, project_b, brand_idea_b
    ):
        search = _create_search(project_b, brand_idea_b)
        result = _create_domain_result(
            project_b, search, domain="theirs.ai", available=True
        )

        response = auth_client_a.post(
            f"/api/v1/domains/{result.id}/check-claims/",
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert DomainClaim.objects.filter(domain_result=result).count() == 0

    def test_check_claims_unauthenticated(self, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )
        client = APIClient()
        response = client.post(
            f"/api/v1/domains/{result.id}/check-claims/",
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestListDomainClaims:
    def test_list_returns_claims_for_this_domain_result(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )
        _create_domain_claim(result, has_claims=False)
        _create_domain_claim(
            result, has_claims=True, claims_data={"claimId": "abc123", "claims": []}
        )

        response = auth_client_a.get(f"/api/v1/domains/{result.id}/claims/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_list_orders_newest_first(self, auth_client_a, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )
        older = _create_domain_claim(
            result, has_claims=False, checked_at=timezone.now() - timedelta(minutes=5)
        )
        newer = _create_domain_claim(result, has_claims=False)

        response = auth_client_a.get(f"/api/v1/domains/{result.id}/claims/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0]["id"] == str(newer.id)

    def test_list_empty_when_no_checks_run_yet(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )

        response = auth_client_a.get(f"/api/v1/domains/{result.id}/claims/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []

    def test_list_other_users_domain_fails(
        self, auth_client_a, project_b, brand_idea_b
    ):
        search = _create_search(project_b, brand_idea_b)
        result = _create_domain_result(
            project_b, search, domain="theirs.ai", available=True
        )

        response = auth_client_a.get(f"/api/v1/domains/{result.id}/claims/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_unauthenticated(self, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(
            project_a, search, domain="ledgerflow.ai", available=True
        )
        client = APIClient()
        response = client.get(f"/api/v1/domains/{result.id}/claims/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

class TestSimulateRegistration:
    def test_simulate_registration_success(self, auth_client_a, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)
        project_a.status = LaunchProject.Status.READY
        project_a.save(update_fields=["status"])

        with _mock_registration_namecom() as MockClient:
            instance = MockClient.return_value
            instance.register_domain.return_value = {"orderId": "sb-12345"}
            response = auth_client_a.post(
                f"/api/v1/domains/{result.id}/simulate-registration/",
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["domain_id"] == str(result.id)

        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS
        assert task.result["simulated"] is True
        assert task.result["order_id"] == "sb-12345"

    def test_simulate_registration_missing_order_id_falls_back(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)
        project_a.status = LaunchProject.Status.READY
        project_a.save(update_fields=["status"])

        with _mock_registration_namecom() as MockClient:
            instance = MockClient.return_value
            instance.register_domain.return_value = {}
            response = auth_client_a.post(
                f"/api/v1/domains/{result.id}/simulate-registration/",
                format="json",
            )

        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS
        assert task.result["order_id"] == f"sandbox-{result.domain}"

    def test_simulate_registration_not_ready_returns_409(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)
        # project_a.status defaults to DRAFT — never advanced to READY.
        response = auth_client_a.post(
            f"/api/v1/domains/{result.id}/simulate-registration/",
            format="json",
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "CONFLICT"

    def test_simulate_registration_provider_timeout_marks_task_failed(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)
        project_a.status = LaunchProject.Status.READY
        project_a.save(update_fields=["status"])

        with _mock_registration_namecom() as MockClient:
            instance = MockClient.return_value
            instance.register_domain.side_effect = NameComTimeoutError("timed out")
            response = auth_client_a.post(
                f"/api/v1/domains/{result.id}/simulate-registration/",
                format="json",
            )

        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "EXTERNAL_API_TIMEOUT"

    def test_simulate_registration_provider_error_marks_task_failed(
        self, auth_client_a, project_a, brand_idea_a
    ):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)
        project_a.status = LaunchProject.Status.READY
        project_a.save(update_fields=["status"])

        with _mock_registration_namecom() as MockClient:
            instance = MockClient.return_value
            instance.register_domain.side_effect = NameComAPIError("server error")
            response = auth_client_a.post(
                f"/api/v1/domains/{result.id}/simulate-registration/",
                format="json",
            )

        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "EXTERNAL_API_ERROR"

    def test_simulate_registration_production_base_url_fails_loudly(
        self, auth_client_a, project_a, brand_idea_a, settings
    ):
        """
        The actual safety mechanism under test: if NAMECOM_TEST_BASE_URL
        is ever misconfigured to a production-shaped host, the task must
        fail loudly with INTERNAL_ERROR — not silently place a real
        order, and not crash uncaught (this is the bug the __init__
        try/except above fixes).
        """
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)
        project_a.status = LaunchProject.Status.READY
        project_a.save(update_fields=["status"])

        settings.NAMECOM_TEST_BASE_URL = "https://api.name.com/core/v1"

        response = auth_client_a.post(
            f"/api/v1/domains/{result.id}/simulate-registration/",
            format="json",
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "INTERNAL_ERROR"

    def test_guard_refuses_production_base_url_directly(self, settings):
        """Service-level unit test of the guard, independent of task/view wiring."""
        settings.NAMECOM_TEST_BASE_URL = "https://api.name.com/core/v1"
        with pytest.raises(DomainRegistrationSimulationGuardError):
            DomainRegistrationSimulationService()

    def test_guard_refuses_injected_production_client(self):
        production_client = NameComClient(
            username="u", token="t", base_url="https://api.name.com/core/v1"
        )
        with pytest.raises(DomainRegistrationSimulationGuardError):
            DomainRegistrationSimulationService(namecom_client=production_client)

    def test_simulate_registration_other_users_domain_fails(
        self, auth_client_a, project_b, brand_idea_b
    ):
        search = _create_search(project_b, brand_idea_b)
        result = _create_domain_result(project_b, search, domain="theirs.ai", available=True)
        project_b.status = LaunchProject.Status.READY
        project_b.save(update_fields=["status"])

        response = auth_client_a.post(
            f"/api/v1/domains/{result.id}/simulate-registration/",
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_simulate_registration_unauthenticated(self, project_a, brand_idea_a):
        search = _create_search(project_a, brand_idea_a)
        result = _create_domain_result(project_a, search, domain="ledgerflow.ai", available=True)
        client = APIClient()
        response = client.post(
            f"/api/v1/domains/{result.id}/simulate-registration/",
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED