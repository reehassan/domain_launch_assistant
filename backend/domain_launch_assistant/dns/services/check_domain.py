# domain_launch_assistant/dns/services/check_domain.py

import socket

from django.db import transaction
from django.utils import timezone

from domain_launch_assistant.dns.models import DomainCheck
from domain_launch_assistant.domains.models import DomainResult
from domain_launch_assistant.launches.models import LaunchProject


class CheckDomainError(Exception):
    """
    Base exception for a domain check run that could not be completed
    as a whole. Subclassed so the view can map to the right
    api-contract.md error code — same pattern as DomainSearchError.
    """
    pass


class CheckDomainUnsupportedTypeError(CheckDomainError):
    """
    Raised when a requested check_type has no implementation to run
    against yet. Currently only DNS_CONFIGURATION — there's no
    configure-dns/ endpoint yet, so there's nothing to validate
    configured records against. Maps to VALIDATION_ERROR.
    """
    pass


class CheckDomainService:
    """
    Runs the requested DomainCheck types against a project's selected
    domain result and persists one DomainCheck row per requested type.

    Synchronous today, same as DomainSearchService — the view fakes a
    task_id until Celery is wired into both endpoints together in a
    later pass.
    """

    # check_types with no implementation yet.
    UNSUPPORTED_CHECK_TYPES = {DomainCheck.CheckType.DNS_CONFIGURATION}

    def run_checks(
        self,
        project: LaunchProject,
        domain_result: DomainResult,
        check_types: list[str],
    ) -> list[DomainCheck]:
        unsupported = [ct for ct in check_types if ct in self.UNSUPPORTED_CHECK_TYPES]
        if unsupported:
            raise CheckDomainUnsupportedTypeError(
                f"Check type(s) not yet supported: {', '.join(unsupported)}"
            )

        with transaction.atomic():
            return [
                self._HANDLERS[check_type](self, project, domain_result)
                for check_type in check_types
            ]

    def _run_dns_resolution(
        self,
        project: LaunchProject,
        domain_result: DomainResult,
    ) -> DomainCheck:
        try:
            resolved_ip = socket.gethostbyname(domain_result.domain)
        except socket.gaierror:
            # Ran successfully — domain simply doesn't resolve yet.
            # This is FAIL, not ERROR: data-model.md §6 — the check
            # completed, the configuration is just not there.
            return DomainCheck.objects.create(
                project=project,
                domain_result=domain_result,
                check_type=DomainCheck.CheckType.DNS_RESOLUTION,
                status=DomainCheck.Status.FAIL,
                record_type="A",
                record_name="@",
                message="Domain does not currently resolve.",
                checked_at=timezone.now(),
            )
        except OSError as exc:
            # The lookup itself couldn't complete — network/resolver
            # issue, not a configuration verdict. ERROR, not FAIL.
            return DomainCheck.objects.create(
                project=project,
                domain_result=domain_result,
                check_type=DomainCheck.CheckType.DNS_RESOLUTION,
                status=DomainCheck.Status.ERROR,
                message=f"DNS resolution check could not be completed: {exc}",
                checked_at=timezone.now(),
            )

        return DomainCheck.objects.create(
            project=project,
            domain_result=domain_result,
            check_type=DomainCheck.CheckType.DNS_RESOLUTION,
            status=DomainCheck.Status.PASS,
            record_type="A",
            record_name="@",
            actual_value=resolved_ip,
            message="Domain resolves correctly.",
            checked_at=timezone.now(),
        )

    def _run_domain_readiness(
        self,
        project: LaunchProject,
        domain_result: DomainResult,
    ) -> DomainCheck:
        # Aggregate check: is this still the project's selected domain,
        # and is it still marked available. No external call — reads
        # local state only, so ERROR isn't a reachable outcome here.
        is_selected = project.selected_domain_id == domain_result.id
        is_available = domain_result.status == DomainResult.Status.AVAILABLE

        if is_selected and is_available:
            return DomainCheck.objects.create(
                project=project,
                domain_result=domain_result,
                check_type=DomainCheck.CheckType.DOMAIN_READINESS,
                status=DomainCheck.Status.PASS,
                message="Domain is ready for launch.",
                checked_at=timezone.now(),
            )

        reasons = []
        if not is_selected:
            reasons.append("domain is not the project's selected domain")
        if not is_available:
            reasons.append("domain is no longer marked available")

        return DomainCheck.objects.create(
            project=project,
            domain_result=domain_result,
            check_type=DomainCheck.CheckType.DOMAIN_READINESS,
            status=DomainCheck.Status.FAIL,
            message="Domain is not ready for launch: " + "; ".join(reasons),
            checked_at=timezone.now(),
        )

    _HANDLERS = {
        DomainCheck.CheckType.DNS_RESOLUTION: _run_dns_resolution,
        DomainCheck.CheckType.DOMAIN_READINESS: _run_domain_readiness,
    }