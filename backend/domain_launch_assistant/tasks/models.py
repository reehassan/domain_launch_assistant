import uuid

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

    def __str__(self):
        return f"{self.task_id} ({self.status})"