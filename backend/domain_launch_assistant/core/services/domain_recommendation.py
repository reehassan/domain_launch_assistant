# domain_launch_assistant/domains/services/domain_recommendation.py

from django.db import transaction

from domain_launch_assistant.core.integrations.gemini.client import GeminiClient
from domain_launch_assistant.domains.models import DomainRecommendation, DomainResult
from domain_launch_assistant.launches.models import LaunchProject


class DomainRecommendationError(Exception):
    """
    Raised when Gemini's recommendation violates application business
    rules (e.g. references a domain that isn't actually available for
    this project). Maps to AI_GENERATION_FAILED, same as a malformed
    Gemini response — from the caller's perspective both mean "we can't
    trust this output, nothing gets persisted."
    """
    pass


class DomainRecommendationService:
    """
    Handles the complete domain-recommendation workflow.

    Responsibilities:
    - Call GeminiClient with the project's AVAILABLE domains.
    - Validate the recommendation references a real, available domain.
    - Create the DomainRecommendation record.

    Mirrors BrandGenerationService's shape.
    """

    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini_client = gemini_client or GeminiClient()

    @transaction.atomic
    def recommend_domain(self, project: LaunchProject) -> DomainRecommendation:
        available_domains = list(
            DomainResult.objects.filter(
                project=project,
                status=DomainResult.Status.AVAILABLE,
            )
        )

        # The view already enforces this via 400, but the service
        # re-checks so it stays safe to call directly (e.g. from tests)
        # without duplicating that check at every call site.
        if not available_domains:
            raise DomainRecommendationError(
                "No available domains to recommend from."
            )

        result = self.gemini_client.recommend_domain(
            business_description=project.business_description,
            domains=[
                {"id": str(d.id), "domain": d.domain}
                for d in available_domains
            ],
        )

        recommended_id = result["recommended_domain_id"].strip()
        reasoning = result["reasoning"].strip()

        if not reasoning:
            raise DomainRecommendationError(
                "Generated recommendation reasoning cannot be empty."
            )

        by_id = {str(d.id): d for d in available_domains}
        recommended_domain = by_id.get(recommended_id)
        if recommended_domain is None:
            raise DomainRecommendationError(
                f"Gemini recommended domain_id '{recommended_id}', which is "
                "not one of the project's available domains."
            )

        return DomainRecommendation.objects.create(
            project=project,
            recommended_domain=recommended_domain,
            reasoning=reasoning,
        )