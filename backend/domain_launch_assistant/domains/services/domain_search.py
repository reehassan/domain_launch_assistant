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
    pass


class DomainSearchTimeoutError(DomainSearchError):
    """The provider did not respond in time. Maps to EXTERNAL_API_TIMEOUT."""
    pass


class DomainSearchProviderError(DomainSearchError):
    """The provider responded with an error. Maps to EXTERNAL_API_ERROR."""
    pass


class DomainSearchInputError(DomainSearchError):
    """Invalid input (e.g. unslugifiable brand name). Maps to VALIDATION_ERROR."""
    pass


class DomainSearchService:
    """
    Split into two steps so the DomainSearch row can exist (as PENDING)
    before a Celery task ever runs — create_pending_search() is called
    synchronously from the view, run_search() is called from the task
    body against that already-persisted row.
    """

    def __init__(self, availability_service: AvailabilityService | None = None):
        self.availability_service = availability_service or AvailabilityService()

    def create_pending_search(
        self,
        project: LaunchProject,
        brand_idea: BrandIdea,
        extensions: list[str],
    ) -> DomainSearch:
        return DomainSearch.objects.create(
            project=project,
            brand_idea=brand_idea,
            status=DomainSearch.Status.PENDING,
            requested_extensions=extensions,
        )

    def run_search(self, search: DomainSearch) -> DomainSearch:
        """
        Runs the actual provider check for an already-created search row.
        Raises DomainSearchTimeoutError, DomainSearchProviderError, or
        DomainSearchInputError on failure — the search row is marked
        FAILED with an error_message in every case, same as before.
        """
        search.status = DomainSearch.Status.PROCESSING
        search.started_at = timezone.now()
        search.save(update_fields=["status", "started_at"])

        try:
            normalized_results = self.availability_service.check_domains(
                brand_name=search.brand_idea.name,
                extensions=search.requested_extensions,
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
                    project=search.project,
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