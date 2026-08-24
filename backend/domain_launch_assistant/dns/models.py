# domain_launch_assistant/dns/models.py

import uuid

from django.db import models


class DomainCheck(models.Model):
    """
    A technical DNS/domain check used to determine launch readiness
    for a selected domain. See data-model.md §6.
    """

    class CheckType(models.TextChoices):
        DNS_CONFIGURATION = "DNS_CONFIGURATION", "DNS Configuration"
        DNS_RESOLUTION = "DNS_RESOLUTION", "DNS Resolution"
        DOMAIN_READINESS = "DOMAIN_READINESS", "Domain Readiness"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PASS = "PASS", "Pass"
        FAIL = "FAIL", "Fail"
        ERROR = "ERROR", "Error"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    project = models.ForeignKey(
        "launches.LaunchProject",
        on_delete=models.CASCADE,
        related_name="domain_checks",
    )

    # PROTECT, not CASCADE: data-model.md §8 calls this out explicitly —
    # "Preserve check history". Deleting a DomainResult must not silently
    # wipe its check history.
    domain_result = models.ForeignKey(
        "domains.DomainResult",
        on_delete=models.PROTECT,
        related_name="checks",
    )

    check_type = models.CharField(
        max_length=32,
        choices=CheckType.choices,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # DNS-specific fields. Per data-model.md §6: "DNS-specific fields
    # should only be populated for DNS checks" — left null for
    # DOMAIN_READINESS checks, which aggregate rather than inspect a
    # single record. Not enforced at the DB level; enforced wherever
    # these get constructed (service/serializer).
    record_type = models.CharField(max_length=16, null=True, blank=True)
    record_name = models.CharField(max_length=255, null=True, blank=True)
    expected_value = models.TextField(null=True, blank=True)
    actual_value = models.TextField(null=True, blank=True)

    message = models.TextField(null=True, blank=True)

    # Null until the Celery task actually runs the check.
    checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["project"], name="dc_project_idx"),
            models.Index(fields=["domain_result"], name="dc_domain_result_idx"),
            # Workflow index — data-model.md §11: "DomainCheck(project_id, status)"
            models.Index(fields=["project", "status"], name="dc_project_status_idx"),
        ]
        ordering = ["-created_at"]

    def clean(self):
        from django.core.exceptions import ValidationError

        # Ownership integrity — data-model.md §10:
        # DomainCheck.project must equal DomainCheck.domain_result.project
        if self.domain_result_id and self.project_id != self.domain_result.project_id:
            raise ValidationError(
                {"project": "DomainCheck.project must match its domain_result's project."}
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.check_type} [{self.status}] - {self.domain_result_id}"