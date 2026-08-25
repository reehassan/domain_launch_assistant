# domain_launch_assistant/dns/services/check_domain.py

import socket

from django.utils import timezone

from domain_launch_assistant.dns.models import DomainCheck
from domain_launch_assistant.domains.models import DomainResult
from domain_launch_assistant.launches.models import LaunchProject


class CheckDomainError(Exception):
    pass


class CheckDomainUnsupportedTypeError(CheckDomainError):
    """Maps to VALIDATION_ERROR. Checked synchronously in the view,
    before any DomainCheck rows exist — there's nothing async about a
    static set-membership check."""
    pass


class CheckDomainService:
    """
    Split like DomainSearchService: validate + create PENDING
    DomainCheck rows synchronously (from the view), then run the
    actual checks against those rows from a background task.
    """

    UNSUPPORTED_CHECK_TYPES = {DomainCheck.CheckType.DNS_CONFIGURATION}

    @classmethod
    def validate_check_types(cls, check_types: list[str]) -> None:
        unsupported = [ct for ct in check_types if ct in cls.UNSUPPORTED_CHECK_TYPES]
        if unsupported:
            raise CheckDomainUnsupportedTypeError(
                f"Check type(s) not yet supported: {', '.join(unsupported)}"
            )

    def create_pending_checks(
        self,
        project: LaunchProject,
        domain_result: DomainResult,
        check_types: list[str],
    ) -> list[DomainCheck]:
        return [
            DomainCheck.objects.create(
                project=project,
                domain_result=domain_result,
                check_type=check_type,
                status=DomainCheck.Status.PENDING,
            )
            for check_type in check_types
        ]

    def run_checks(self, checks: list[DomainCheck]) -> list[DomainCheck]:
        return [self._HANDLERS[check.check_type](self, check) for check in checks]

    def _run_dns_resolution(self, check: DomainCheck) -> DomainCheck:
        domain_result = check.domain_result
        try:
            resolved_ip = socket.gethostbyname(domain_result.domain)
        except socket.gaierror:
            # Ran successfully — domain simply doesn't resolve yet.
            # FAIL, not ERROR: data-model.md §6.
            check.status = DomainCheck.Status.FAIL
            check.record_type = "A"
            check.record_name = "@"
            check.message = "Domain does not currently resolve."
        except OSError as exc:
            # The lookup itself couldn't complete — network/resolver
            # issue, not a configuration verdict. ERROR, not FAIL.
            # This is the one place a "provider failure" can happen in
            # this service, and it was already handled before Day 6 —
            # nothing new needed here for the async conversion.
            check.status = DomainCheck.Status.ERROR
            check.message = f"DNS resolution check could not be completed: {exc}"
        else:
            check.status = DomainCheck.Status.PASS
            check.record_type = "A"
            check.record_name = "@"
            check.actual_value = resolved_ip
            check.message = "Domain resolves correctly."

        check.checked_at = timezone.now()
        check.save(update_fields=[
            "status", "record_type", "record_name", "actual_value", "message", "checked_at",
        ])
        return check

    def _run_domain_readiness(self, check: DomainCheck) -> DomainCheck:
        project = check.project
        domain_result = check.domain_result
        is_selected = project.selected_domain_id == domain_result.id
        is_available = domain_result.status == DomainResult.Status.AVAILABLE

        if is_selected and is_available:
            check.status = DomainCheck.Status.PASS
            check.message = "Domain is ready for launch."
        else:
            reasons = []
            if not is_selected:
                reasons.append("domain is not the project's selected domain")
            if not is_available:
                reasons.append("domain is no longer marked available")
            check.status = DomainCheck.Status.FAIL
            check.message = "Domain is not ready for launch: " + "; ".join(reasons)

        check.checked_at = timezone.now()
        check.save(update_fields=["status", "message", "checked_at"])
        return check

    _HANDLERS = {
        DomainCheck.CheckType.DNS_RESOLUTION: _run_dns_resolution,
        DomainCheck.CheckType.DOMAIN_READINESS: _run_domain_readiness,
    }