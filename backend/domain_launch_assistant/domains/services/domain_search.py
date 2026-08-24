# domain_launch_assistant/domains/services/domain_search.py

from django.db import transaction
from django.utils import timezone

from domain_launch_assistant.brands.models import BrandIdea
from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComTimeoutError,
)
from domain_launch_assistant.domains.models import DomainResult, DomainSearch
from domain_launch_assistant.domains.services.availability import AvailabilityService
from domain_launch_assistant.launches.models import LaunchProject


class DomainSearchError(Exception):
    """
    Base exception for a domain search that could not be completed as a
    whole. Subclassed so views can distinguish provider timeouts from
    provider errors from invalid brand names, per api-contract.md
    section 26 (External API Failure Contract) and section 27-style
    AI failure handling.
    """
    pass


class DomainSearchTimeoutError(DomainSearchError):
    """The provider did not respond in time. Maps to EXTERNAL_API_TIMEOUT."""
    pass


class DomainSearchProviderError(DomainSearchError):
    """The provider responded with an error. Maps to EXTERNAL_API_ERROR."""
    pass


class DomainSearchInputError(DomainSearchError):
    """The search could not proceed due to invalid input (e.g. brand name
    with no valid domain-label characters). Maps to VALIDATION_ERROR."""
    pass


class DomainSearchService:
    """
    Handles the complete domain-search workflow.

    Responsibilities:
    - Create the DomainSearch record.
    - Call AvailabilityService (which calls NameComClient).
    - Validate and bulk-create DomainResult records from normalized results.
    - Mark the search COMPLETED or FAILED.
    - Ensure DomainResult writes are atomic.

    This service knows about Django models.
    AvailabilityService/NameComClient do not.
    """

    def __init__(self, availability_service: AvailabilityService | None = None):
        self.availability_service = availability_service or AvailabilityService()

    def start_search(
        self,
        project: LaunchProject,
        brand_idea: BrandIdea,
        extensions: list[str],
    ) -> DomainSearch:
        """
        Raises DomainSearchTimeoutError, DomainSearchProviderError, or
        DomainSearchInputError if the search as a whole failed. The
        DomainSearch row is still persisted as FAILED with an
        error_message in every case, so callers/tests can inspect it —
        but no DomainResult rows are created for a failed search.
        """
        search = DomainSearch.objects.create(
            project=project,
            brand_idea=brand_idea,
            status=DomainSearch.Status.PROCESSING,
            requested_extensions=extensions,
            started_at=timezone.now(),
        )

        try:
            normalized_results = self.availability_service.check_domains(
                brand_name=brand_idea.name,
                extensions=extensions,
            )
        except NameComTimeoutError as exc:
            self._mark_failed(search, exc)
            raise DomainSearchTimeoutError(str(exc)) from exc
        except NameComAPIError as exc:
            self._mark_failed(search, exc)
            raise DomainSearchProviderError(str(exc)) from exc
        except ValueError as exc:
            self._mark_failed(search, exc)
            raise DomainSearchInputError(str(exc)) from exc

        with transaction.atomic():
            results_to_create = [
                DomainResult(
                    search=search,
                    project=project,
                    domain=result["domain"],
                    extension=result["extension"],
                    available=result["available"],
                    status=result["status"],
                    provider=result["provider"],
                    checked_at=result["checked_at"],
                    raw_metadata=result["raw_metadata"],
                )
                for result in normalized_results
            ]

            DomainResult.validate_batch(results_to_create)
            DomainResult.objects.bulk_create(results_to_create)

            search.status = DomainSearch.Status.COMPLETED
            search.completed_at = timezone.now()
            search.save(update_fields=["status", "completed_at"])

        return search

    @staticmethod
    def _mark_failed(search: DomainSearch, exc: Exception) -> None:
        search.status = DomainSearch.Status.FAILED
        search.error_message = str(exc)
        search.completed_at = timezone.now()
        search.save(update_fields=["status", "error_message", "completed_at"])