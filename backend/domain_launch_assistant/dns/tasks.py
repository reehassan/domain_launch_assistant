# domain_launch_assistant/dns/tasks.py
import json

from celery import shared_task
from rest_framework.renderers import JSONRenderer

from domain_launch_assistant.dns.models import DomainCheck
from domain_launch_assistant.dns.serializers import DomainCheckSerializer
from domain_launch_assistant.dns.services.check_domain import CheckDomainService
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.tasks.models import TaskRecord


@shared_task
def run_domain_checks_task(task_id: str, check_ids: list[str]) -> None:
    """
    check_ids point at DomainCheck rows the view already created as
    PENDING. project.status = VERIFYING_DNS is set here, at the start
    of the task — not in the view — so the frontend never sees
    "verifying" before a worker has actually picked the job up.
    """
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])

    checks = list(DomainCheck.objects.filter(id__in=check_ids))

    project = checks[0].project
    project.status = LaunchProject.Status.VERIFYING_DNS
    project.save(update_fields=["status"])

    # No try/except here: CheckDomainService.run_checks() cannot raise —
    # the one exception type in this service (CheckDomainUnsupportedTypeError)
    # is validated synchronously in the view before this task is ever
    # dispatched, and DNS lookup failures are already caught inside the
    # handlers themselves as FAIL/ERROR check rows, not exceptions.
    CheckDomainService().run_checks(checks)

    rendered = JSONRenderer().render(DomainCheckSerializer(checks, many=True).data)
    task.status = TaskRecord.Status.SUCCESS
    task.result = {"results": json.loads(rendered)}
    task.save(update_fields=["status", "result"])