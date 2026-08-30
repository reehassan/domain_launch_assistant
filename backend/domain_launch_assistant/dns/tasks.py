# domain_launch_assistant/dns/tasks.py
import json
import logging

from celery import shared_task
from rest_framework.renderers import JSONRenderer

from domain_launch_assistant.dns.models import DomainCheck
from domain_launch_assistant.dns.serializers import DomainCheckSerializer
from domain_launch_assistant.dns.services.check_domain import CheckDomainService
from domain_launch_assistant.dns.services.dns_records import (
    DnsRecordsError,
    DnsRecordsGuardError,
    DnsRecordsProviderError,
    DnsRecordsService,
    DnsRecordsTimeoutError,
)
from domain_launch_assistant.domains.models import DomainResult
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.tasks.models import TaskRecord

logger = logging.getLogger(__name__)


@shared_task
def run_domain_checks_task(task_id: str, check_ids: list[str]) -> None:
    """
    check_ids point at DomainCheck rows the view already created as
    PENDING. project.status = VERIFYING_DNS is set here, at the start
    of the task — not in the view — so the frontend never sees
    "verifying" before a worker has actually picked the job up.

    Wrapped in the same try/except Exception -> FAILURE pattern every
    other task in this app uses (audit fix — Ticket 2). This used to
    skip that wrapper on the reasoning that
    CheckDomainService.run_checks() cannot raise — the one exception
    type in that service (CheckDomainUnsupportedTypeError) is validated
    synchronously in the view before this task is ever dispatched, and
    DNS lookup failures are already caught inside the handlers
    themselves as FAIL/ERROR check rows, not exceptions. That reasoning
    is still true for run_checks() itself, but never covered the line
    right before it: `checks[0]` raises an uncaught IndexError if
    check_ids is ever empty, and with no safety net the TaskRecord was
    left stuck PROCESSING forever — the frontend's poll loop had no
    FAILURE state to ever land on. This wrapper is defense-in-depth
    against that case (and anything else unexpected), not a sign
    run_checks() is now expected to raise routinely.
    """
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])

    try:
        checks = list(DomainCheck.objects.filter(id__in=check_ids))
        project = checks[0].project
        project.status = LaunchProject.Status.VERIFYING_DNS
        project.save(update_fields=["status"])

        ran_checks = CheckDomainService().run_checks(checks)

        # Project only reaches READY once every requested check type has
        # actually PASSed — a single FAIL or ERROR must not silently let
        # the founder past DNS verification into Feature 5/6. On anything
        # less than all-PASS, project.status stays VERIFYING_DNS (already
        # set above) so the founder can re-run check/ after fixing DNS.
        if all(c.status == DomainCheck.Status.PASS for c in ran_checks):
            project.status = LaunchProject.Status.READY
            project.save(update_fields=["status"])

        rendered = JSONRenderer().render(DomainCheckSerializer(checks, many=True).data)
    except Exception:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = "Something went wrong. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        logger.exception(
            "Unhandled error in run_domain_checks_task",
            extra={"task_id": task_id, "check_ids": check_ids},
        )
        return

    task.status = TaskRecord.Status.SUCCESS
    task.result = {"results": json.loads(rendered)}
    task.save(update_fields=["status", "result"])


@shared_task
def create_dns_record_task(task_id: str, domain_result_id: str, record_data: dict) -> None:
    """
    Background counterpart of DnsRecordCreateView. domain_result_id
    points at an already-persisted DomainResult; record_data is the
    already-validated serializer output (host/type/answer/ttl/priority).
    DnsRecordsService builds its own sandbox-only NameComClient
    internally — never the production client used by
    AvailabilityService/DomainClaimsService. Nothing is persisted beyond
    TaskRecord: no local model, no LaunchProject.status change — name.com
    is the only source of truth for DNS records, same discipline
    simulate_registration_task already uses for the registration result.
    """
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])

    domain_result = DomainResult.objects.get(id=domain_result_id)

    try:
        record = DnsRecordsService().create_record(
            domain_result,
            host=record_data["host"],
            record_type=record_data["type"],
            answer=record_data["answer"],
            ttl=record_data["ttl"],
            priority=record_data.get("priority"),
        )
    except DnsRecordsGuardError as exc:
        # The sandbox/production guard tripped. Configuration safety
        # violation, not a routine provider failure — must fail loudly
        # with its own code, same as simulate_registration_task's
        # handling of DomainRegistrationSimulationGuardError.
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DnsRecordsTimeoutError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_TIMEOUT"
        task.error_message = "The DNS provider did not respond. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DnsRecordsProviderError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = "DNS record creation is temporarily unavailable."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DnsRecordsError as exc:
        # Defensive catch-all for the base class, same pattern used by
        # check_domain_claims_task's DomainClaimsError handler.
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except Exception:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = "Something went wrong. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        logger.exception(
            "Unhandled error in create_dns_record_task",
            extra={"task_id": task_id, "domain_result_id": domain_result_id},
        )
        return

    task.status = TaskRecord.Status.SUCCESS
    # Plain dict of JSON-primitive values (str/int) — no model involved,
    # so no serializer round-trip needed, same as simulate_registration_task.
    task.result = record
    task.save(update_fields=["status", "result"])

@shared_task
def update_dns_record_task(task_id: str, domain_result_id: str, record_id: int, record_data: dict) -> None:
    """
    Background counterpart of DnsRecordUpdateView. Same error-handling
    shape as create_dns_record_task — see that task's docstring for why
    nothing beyond TaskRecord is persisted.
    """
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])
    domain_result = DomainResult.objects.get(id=domain_result_id)
    try:
        record = DnsRecordsService().update_record(
            domain_result,
            record_id,
            host=record_data["host"],
            record_type=record_data["type"],
            answer=record_data["answer"],
            ttl=record_data["ttl"],
            priority=record_data.get("priority"),
        )
    except DnsRecordsGuardError as exc:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DnsRecordsTimeoutError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_TIMEOUT"
        task.error_message = "The DNS provider did not respond. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DnsRecordsProviderError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = "DNS record update is temporarily unavailable."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DnsRecordsError as exc:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except Exception:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = "Something went wrong. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        logger.exception(
            "Unhandled error in update_dns_record_task",
            extra={"task_id": task_id, "domain_result_id": domain_result_id, "record_id": record_id},
        )
        return
    task.status = TaskRecord.Status.SUCCESS
    task.result = record
    task.save(update_fields=["status", "result"])


@shared_task
def delete_dns_record_task(task_id: str, domain_result_id: str, record_id: int) -> None:
    """
    Background counterpart of DnsRecordDeleteView. Same error-handling
    shape as create_dns_record_task/update_dns_record_task. On success,
    task.result is a small plain dict (name.com's delete response body
    is empty, so there's nothing from the provider to echo back) — just
    enough for the frontend to confirm which record_id was removed.
    """
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])
    domain_result = DomainResult.objects.get(id=domain_result_id)
    try:
        DnsRecordsService().delete_record(domain_result, record_id)
    except DnsRecordsGuardError as exc:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DnsRecordsTimeoutError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_TIMEOUT"
        task.error_message = "The DNS provider did not respond. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DnsRecordsProviderError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = "DNS record deletion is temporarily unavailable."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DnsRecordsError as exc:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except Exception:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = "Something went wrong. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        logger.exception(
            "Unhandled error in delete_dns_record_task",
            extra={"task_id": task_id, "domain_result_id": domain_result_id, "record_id": record_id},
        )
        return
    task.status = TaskRecord.Status.SUCCESS
    task.result = {"record_id": record_id, "deleted": True}
    task.save(update_fields=["status", "result"])