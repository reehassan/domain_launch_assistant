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


class CheckDomainMissingHandlerError(CheckDomainError):
    """
    Raised if run_checks() is ever asked to run a check_type with no
    entry in _HANDLERS. Should be unreachable in practice — every
    check_type not in _HANDLERS is currently also listed in
    UNSUPPORTED_CHECK_TYPES, which validate_check_types() rejects
    synchronously in the view before any DomainCheck row is created.
    This exists only so that if that guard is ever loosened without a
    handler being added at the same time, the failure is an explicit,
    named error instead of a bare KeyError — and, since Ticket 2, this
    is raised from inside run_domain_checks_task's try/except Exception
    block, so it surfaces as a normal TaskRecord FAILURE (logged via
    logger.exception) rather than leaving the task stuck PROCESSING.
    """
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
        expected_value: str | None = None,
    ) -> list[DomainCheck]:
        """
        Ticket 13: expected_value is stamped onto the DNS_RESOLUTION row
        at creation time (not looked up later from anywhere) — it's the
        caller-supplied IP the check will be graded against. Other
        check types (DOMAIN_READINESS) ignore it; per data-model.md §6
        DNS-specific fields stay null for non-DNS checks.
        """
        checks = []
        for check_type in check_types:
            create_kwargs = dict(
                project=project,
                domain_result=domain_result,
                check_type=check_type,
                status=DomainCheck.Status.PENDING,
            )
            if check_type == DomainCheck.CheckType.DNS_RESOLUTION:
                create_kwargs["expected_value"] = expected_value
            checks.append(DomainCheck.objects.create(**create_kwargs))
        return checks

    def run_checks(self, checks: list[DomainCheck]) -> list[DomainCheck]:
        results = []
        for check in checks:
            handler = self._HANDLERS.get(check.check_type)
            if handler is None:
                raise CheckDomainMissingHandlerError(
                    f"No handler registered for check_type={check.check_type!r}. "
                    "This check_type was accepted by validate_check_types() but "
                    "has no corresponding entry in CheckDomainService._HANDLERS."
                )
            results.append(handler(self, check))
        return results

    def _run_dns_resolution(self, check: DomainCheck) -> DomainCheck:
        """
        Ticket 13: this used to PASS on any successful resolution —
        "does this hostname resolve to *anything*" — which let an
        unrelated, unowned third-party server pass the check. It now
        verifies "does this hostname resolve to what the caller
        expects", via check.expected_value (set in
        create_pending_checks() from the request body; the request
        serializer requires it whenever DNS_RESOLUTION is requested, so
        it's never empty here in practice).
        """
        domain_result = check.domain_result
        expected_ip = check.expected_value
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
            check.status = DomainCheck.Status.ERROR
            check.message = f"DNS resolution check could not be completed: {exc}"
        else:
            check.record_type = "A"
            check.record_name = "@"
            check.actual_value = resolved_ip
            if resolved_ip == expected_ip:
                check.status = DomainCheck.Status.PASS
                check.message = "Domain resolves to the expected IP."
            else:
                check.status = DomainCheck.Status.FAIL
                check.message = (
                    f"Domain resolves to {resolved_ip}, which does not match "
                    f"the expected value {expected_ip}."
                )

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