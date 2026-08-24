# domain_launch_assistant/domains/models.py

import uuid

from django.db import models


class DomainSearch(models.Model):
    """
    One domain availability search performed for a project,
    optionally scoped to a specific brand idea.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    project = models.ForeignKey(
        "launches.LaunchProject",
        on_delete=models.CASCADE,
        related_name="domain_searches",
    )
    brand_idea = models.ForeignKey(
        "brands.BrandIdea",
        on_delete=models.CASCADE,
        related_name="domain_searches",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_extensions = models.JSONField(default=list)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "created_at"], name="ds_project_created_idx"),
            models.Index(fields=["project", "status"], name="ds_project_status_idx"),
            models.Index(fields=["brand_idea", "created_at"], name="ds_brand_created_idx"),
        ]
        ordering = ["-created_at"]

    def clean(self):
        from django.core.exceptions import ValidationError

        # A search cannot reference a brand from another project.
        if self.brand_idea_id and self.brand_idea.project_id != self.project_id:
            raise ValidationError(
                "brand_idea must belong to the same project as the search."
            )

    def __str__(self):
        return f"DomainSearch({self.id}) - {self.status}"


class DomainResult(models.Model):
    """
    One domain name returned by a DomainSearch, with its
    availability state from the provider (e.g. name.com).
    """

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        TAKEN = "TAKEN", "Taken"
        UNKNOWN = "UNKNOWN", "Unknown"
        CHECK_FAILED = "CHECK_FAILED", "Check failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    search = models.ForeignKey(
        DomainSearch,
        on_delete=models.CASCADE,
        related_name="results",
    )
    project = models.ForeignKey(
        "launches.LaunchProject",
        on_delete=models.CASCADE,
        related_name="domain_results",
    )
    domain = models.CharField(max_length=255)
    extension = models.CharField(max_length=32)
    available = models.BooleanField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )
    provider = models.CharField(max_length=100)
    checked_at = models.DateTimeField()
    raw_metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "domain"], name="dr_project_domain_idx"),
            models.Index(fields=["search", "domain"], name="dr_search_domain_idx"),
            models.Index(fields=["project", "available"], name="dr_project_avail_idx"),
            models.Index(fields=["domain", "checked_at"], name="dr_domain_checked_idx"),
            models.Index(fields=["project", "extension"], name="dr_project_ext_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["search", "domain"],
                name="uniq_search_domain",
            ),
        ]
        ordering = ["-checked_at"]

    def clean(self):
        from django.core.exceptions import ValidationError

        # A result must belong to the same project as its parent search.
        if self.search_id and self.project_id != self.search.project_id:
            raise ValidationError(
                "DomainResult.project must match its parent search's project."
            )

        # available=True must correspond to status=AVAILABLE, and vice versa.
        if self.available and self.status != self.Status.AVAILABLE:
            raise ValidationError(
                "available=True requires status=AVAILABLE."
            )
        if not self.available and self.status == self.Status.AVAILABLE:
            raise ValidationError(
                "status=AVAILABLE requires available=True."
            )

    def save(self, *args, **kwargs):
        if self.domain:
            self.domain = self.domain.lower().strip()
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def validate_batch(cls, instances: list["DomainResult"]) -> None:
        """
        Runs clean() on each instance before a bulk_create, since
        bulk_create bypasses save()/full_clean() entirely. Raises on
        the first invalid instance.
        """
        for instance in instances:
            instance.domain = instance.domain.lower().strip()
            instance.clean()

    def __str__(self):
        return f"{self.domain} ({self.status})"