from django.core.exceptions import ValidationError
from django.db import models

from domain_launch_assistant.launches.models import LaunchProject


class TaskRecord(models.Model):
    """
    Tracks the lifecycle of a Celery task dispatched from an API view,
    so GET /api/v1/tasks/{task_id}/ has something to read.

    task_id is the Celery task's own UUID (from .delay().id) — not a
    separate model id — so callers query by exactly the value the
    dispatching view returned. No user FK: ownership is checked via
    project.user, matching brands/domains/dns rather than introducing
    a second, independently-driftable ownership pointer.

    NOTE: project == domain_result.project (when domain_result is set)
    is an enforced invariant via clean(). Every call site creates
    TaskRecord internally from a service, never from user input.

    clean() validates that when a domain_result is attached to a task,
    it belongs to the same LaunchProject stored on the task. This keeps
    the cross-FK ownership relationship consistent with the rest of
    the data model.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        SUCCESS = "SUCCESS", "Success"
        FAILURE = "FAILURE", "Failure"

    task_id = models.UUIDField(primary_key=True, editable=False)
    project = models.ForeignKey(
        LaunchProject,
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    # Optional: which DomainResult this task is about. Only set by
    # dispatch views whose action is legitimately independent per
    # domain (currently just claims-check — see
    # has_active_task_for_domain below). Left null for project-wide
    # actions (search, recommend), which keep locking against the
    # whole project via has_active_task, unchanged.
    domain_result = models.ForeignKey(
        "domains.DomainResult",
        on_delete=models.SET_NULL,
        related_name="tasks",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    result = models.JSONField(null=True, blank=True, default=None)
    error_code = models.CharField(max_length=64, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        """
        Ensure the TaskRecord and its DomainResult belong to the same
        LaunchProject.

        A project-wide task can have domain_result=None, so there is
        nothing to validate in that case.
        """
        if (
            self.domain_result_id is not None
            and self.domain_result is not None
            and self.project_id != self.domain_result.project_id
        ):
            raise ValidationError(
                {
                    "domain_result": (
                        "domain_result must belong to the same project as project."
                    )
                }
            )

    @classmethod
    def has_active_task(cls, project) -> bool:
        """
        True if this project has a TaskRecord still PENDING or
        PROCESSING. Used by dispatch views to reject a second
        generate/search/check/recommend/simulate call while one is
        already in flight for the same project — prevents wasted
        provider calls and, once regenerate performs a delete-then-
        create, prevents one task's cleanup from racing another
        task's writes.
        """
        return cls.objects.filter(
            project=project,
            status__in=[cls.Status.PENDING, cls.Status.PROCESSING],
        ).exists()

    @classmethod
    def has_active_task_for_domain(cls, domain_result) -> bool:
        """
        True if this SPECIFIC domain has a TaskRecord still PENDING or
        PROCESSING. Narrower than has_active_task(project) — used only
        by actions that don't touch shared project state, so two of
        them running for two different domains at once is safe.

        Added for the claims-check auto-trigger (DomainClaimsCheck.jsx
        mounts one instance per AVAILABLE domain card and fires a
        check immediately, so N domain cards dispatch N checks near-
        simultaneously): the old project-wide has_active_task() lock
        let only one of those N checks through, 409ing the rest even
        though checking domain A's trademark status has nothing to do
        with checking domain B's. This method fixes that at the root
        instead of papering over it with frontend throttling.

        Only trusts task rows that were actually tagged with this
        domain via TaskRecord.domain_result — a task dispatched by a
        project-wide action (search, recommend) is invisible to this
        check, by design; those keep serializing via has_active_task
        instead.
        """
        return cls.objects.filter(
            domain_result=domain_result,
            status__in=[cls.Status.PENDING, cls.Status.PROCESSING],
        ).exists()

    def __str__(self):
        return f"{self.task_id} ({self.status})"