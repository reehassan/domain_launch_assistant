from django.db import transaction

from domain_launch_assistant.brands.models import BrandIdea
from domain_launch_assistant.core.integrations.gemini.client import GeminiClient
from domain_launch_assistant.launches.models import LaunchProject


class BrandGenerationError(Exception):
    """
    Raised when generated brand ideas violate application business rules.
    """

    pass


class BrandGenerationService:
    """
    Handles the complete brand-generation workflow.

    Responsibilities:
    - Call GeminiClient.
    - Validate application-level business rules.
    - Create BrandIdea records.
    - Ensure database writes are atomic.

    This service knows about Django models.
    GeminiClient does not.
    """

    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini_client = gemini_client or GeminiClient()

    @transaction.atomic
    def generate_brand_ideas(
        self,
        project: LaunchProject,
        count: int,
    ) -> list[BrandIdea]:
        """
        Generate brand ideas for a project and persist them atomically.
        """

        # Regenerate semantics: a prior unselected batch was explicitly
        # rejected by the founder ("Not loving these? Regenerate"), so it
        # is deleted before the new batch is created. This also fixes a
        # correctness bug, not just cleanup: unique_brand_name_per_project_ci
        # is project-wide, not per-batch, so leaving the old batch in
        # place made regeneration fail outright whenever Gemini reused a
        # name from the discarded batch. Once a brand is selected,
        # BrandGenerateView is expected to be unreachable for this
        # project (frontend hides the button), so this delete should
        # never touch a selected brand in practice — but is_selected=False
        # is kept as an explicit safety filter regardless.
        BrandIdea.objects.filter(project=project, is_selected=False).delete()

        result = self.gemini_client.generate_brand_ideas(
            business_description=project.business_description,
            count=count,
        )

        brands = result["brands"]

        self._validate_business_rules(
            brands=brands,
            requested_count=count,
        )

        brand_ideas = [
            BrandIdea(
                project=project,
                name=brand["name"].strip(),
                description=brand["description"].strip(),
            )
            for brand in brands
        ]

        BrandIdea.objects.bulk_create(brand_ideas)

        return brand_ideas

    @staticmethod
    def _validate_business_rules(
        brands: list[dict],
        requested_count: int,
    ) -> None:
        """
        Validate rules that are specific to our application,
        rather than the structure of Gemini's response.
        """

        if len(brands) != requested_count:
            raise BrandGenerationError(
                f"Expected {requested_count} brand ideas, "
                f"but Gemini returned {len(brands)}."
            )

        names = []

        for brand in brands:
            name = brand["name"].strip()
            description = brand["description"].strip()

            if not name:
                raise BrandGenerationError(
                    "Generated brand name cannot be empty."
                )

            if not description:
                raise BrandGenerationError(
                    "Generated brand description cannot be empty."
                )

            names.append(name.casefold())

        if len(names) != len(set(names)):
            raise BrandGenerationError(
                "Generated brand names must be unique."
            )