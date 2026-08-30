import uuid

from django.conf import settings
from django.db import models


class LaunchProject(models.Model):
    """
    Represents a single business launch being worked on by a founder.
    This is the central domain model of the application.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        GENERATING_BRANDS = "GENERATING_BRANDS", "Generating Brands"
        BRANDS_READY = "BRANDS_READY", "Brands Ready"
        CHECKING_DOMAINS = "CHECKING_DOMAINS", "Checking Domains"
        DOMAIN_SELECTED = "DOMAIN_SELECTED", "Domain Selected"
        CONFIGURING_DNS = "CONFIGURING_DNS", "Configuring DNS"
        VERIFYING_DNS = "VERIFYING_DNS", "Verifying DNS"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
        help_text="Project owner.",
    )

    name = models.CharField(
        max_length=255,
        help_text="Internal project name.",
    )

    business_description = models.TextField(
        help_text="Description of the business.",
    )

    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.DRAFT,
        help_text="Current workflow status.",
    )

    # `brands` app now exists, so this FK is live. Run makemigrations/migrate
    # on the `launches` app after adding this field.
    selected_brand = models.ForeignKey(
        "brands.BrandIdea",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="selected_for_projects",
        help_text="Selected brand idea, if any.",
    )
    selected_domain = models.ForeignKey(
        "domains.DomainResult",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="selected_for_projects",
        help_text="Selected domain, if any.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"], name="launch_user_created_idx"),
            models.Index(fields=["user", "status"], name="launch_user_status_idx"),
            models.Index(fields=["updated_at"], name="launch_updated_idx"),
        ]

        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="launchproject_name_not_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(business_description=""),
                name="launchproject_description_not_empty",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.user_id})"

    def clean(self):
        """
        Extra validation beyond what DB constraints can express:
        - selected_brand, when present, must belong to this same project.
        - selected_domain, when present, must belong to this same project.
        The selected_domain check activates once the `domains` app exists
        and that FK is uncommented above.
        """
        from django.core.exceptions import ValidationError

        selected_brand = getattr(self, "selected_brand", None)
        if selected_brand is not None and selected_brand.project_id != self.id:
            raise ValidationError(
                {"selected_brand": "Selected brand must belong to this project."}
            )

        selected_domain = getattr(self, "selected_domain", None)
        if selected_domain is not None and selected_domain.project_id != self.id:
            raise ValidationError(
                {"selected_domain": "Selected domain must belong to this project."}
            )