# domain_launch_assistant/dns/services/dns_records.py

from urllib.parse import urlparse

from django.conf import settings

from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComSandboxGuardError,
    NameComTimeoutError,
)
from domain_launch_assistant.domains.clients.namecom import NameComClient
from domain_launch_assistant.domains.models import DomainResult


class DnsRecordsError(Exception):
    pass


class DnsRecordsTimeoutError(DnsRecordsError):
    """The provider did not respond in time. Maps to EXTERNAL_API_TIMEOUT."""
    pass


class DnsRecordsProviderError(DnsRecordsError):
    """The provider responded with an error. Maps to EXTERNAL_API_ERROR."""
    pass


class DnsRecordsGuardError(DnsRecordsError):
    """
    The sandbox base-url guard refused to run. Must never be treated as a
    routine provider failure — it means the app is configured in a way
    that could otherwise let a "sandbox" call hit production. Maps to
    INTERNAL_ERROR, not EXTERNAL_API_ERROR. Same discipline as
    DomainRegistrationSimulationGuardError.
    """
    pass


class DnsRecordsService:
    """
    Real DNS record management (list + create) against name.com's
    actual DNS Records API — GET/POST /domains/{domainName}/records
    (Core API v1; confirmed against docs.name.com's DNS reference).

    SANDBOX-ONLY, same reasoning and guard mechanism as
    DomainRegistrationSimulationService: a domain in this app is only
    ever registered against name.com's sandbox (registration_simulation.py
    never touches production), so it only exists as a real object on
    api.dev.name.com. Managing its DNS records against production would
    404 — there is nothing there to manage. The guard below is
    duplicated from DomainRegistrationSimulationService rather than
    shared, matching this codebase's existing convention of each service
    owning its own identical error-handling/guard boilerplate (compare
    domain_claims.py vs. registration_simulation.py) rather than
    introducing a shared base class this iteration.

    Persists nothing itself: name.com is the only source of truth for
    DNS records, so unlike DomainCheck/DomainClaim there is no local
    model or migration for this feature. list_records() is a live proxy
    read every time it's called, not a cache.
    """

    def __init__(self, namecom_client: NameComClient | None = None):
        try:
            if namecom_client is not None:
                # Test-only escape hatch for injecting a pre-built client —
                # still runs through the same guard via its base_url, so a
                # caller can't bypass the safety check by constructing its
                # own client and handing it in. Same pattern as
                # DomainRegistrationSimulationService.__init__.
                self._guard_base_url(namecom_client.base_url)
                self.namecom_client = namecom_client
            else:
                self.namecom_client = self._build_sandbox_client()
        except NameComSandboxGuardError as exc:
            raise DnsRecordsGuardError(str(exc)) from exc

    @staticmethod
    def _guard_base_url(base_url: str) -> None:
        host = urlparse(base_url).hostname or ""
        if host != settings.NAMECOM_SANDBOX_HOST:
            raise NameComSandboxGuardError(
                f"Refusing to manage DNS records: configured base URL "
                f"'{base_url}' does not resolve to the sandbox host "
                f"'{settings.NAMECOM_SANDBOX_HOST}'."
            )

    def _build_sandbox_client(self) -> NameComClient:
        self._guard_base_url(settings.NAMECOM_TEST_BASE_URL)
        return NameComClient(
            username=settings.NAMECOM_TEST_USERNAME,
            token=settings.NAMECOM_TEST_API_TOKEN,
            base_url=settings.NAMECOM_TEST_BASE_URL,
        )

    def list_records(self, domain_result: DomainResult) -> list[dict]:
        """
        Raises DnsRecordsTimeoutError / DnsRecordsProviderError on
        provider failure — never returns a fabricated empty list on
        failure, same discipline as DomainClaimsService.check_claims().
        """
        try:
            return self.namecom_client.list_records(domain_result.domain)
        except NameComTimeoutError as exc:
            raise DnsRecordsTimeoutError(str(exc)) from exc
        except NameComAPIError as exc:
            raise DnsRecordsProviderError(str(exc)) from exc

    def create_record(
        self,
        domain_result: DomainResult,
        host: str,
        record_type: str,
        answer: str,
        ttl: int = 300,
        priority: int | None = None,
    ) -> dict:
        """
        Raises DnsRecordsTimeoutError / DnsRecordsProviderError on
        provider failure — the caller (the Celery task) must not
        persist anything on failure, same discipline as
        DomainRegistrationSimulationService.simulate_registration().
        """
        try:
            return self.namecom_client.create_record(
                domain_result.domain,
                host=host,
                record_type=record_type,
                answer=answer,
                ttl=ttl,
                priority=priority,
            )
        except NameComTimeoutError as exc:
            raise DnsRecordsTimeoutError(str(exc)) from exc
        except NameComAPIError as exc:
            raise DnsRecordsProviderError(str(exc)) from exc

    def update_record(
        self,
        domain_result: DomainResult,
        record_id: int,
        host: str,
        record_type: str,
        answer: str,
        ttl: int = 300,
        priority: int | None = None,
    ) -> dict:
        """
        Raises DnsRecordsTimeoutError / DnsRecordsProviderError on
        provider failure — the caller (the Celery task) must not treat
        a failed update as if the old record still stands unmodified,
        same discipline as create_record.
        """
        try:
            return self.namecom_client.update_record(
                domain_result.domain,
                record_id,
                host=host,
                record_type=record_type,
                answer=answer,
                ttl=ttl,
                priority=priority,
            )
        except NameComTimeoutError as exc:
            raise DnsRecordsTimeoutError(str(exc)) from exc
        except NameComAPIError as exc:
            raise DnsRecordsProviderError(str(exc)) from exc

    def delete_record(self, domain_result: DomainResult, record_id: int) -> None:
        """
        Raises DnsRecordsTimeoutError / DnsRecordsProviderError on
        provider failure, same discipline as create_record/update_record.
        """
        try:
            self.namecom_client.delete_record(domain_result.domain, record_id)
        except NameComTimeoutError as exc:
            raise DnsRecordsTimeoutError(str(exc)) from exc
        except NameComAPIError as exc:
            raise DnsRecordsProviderError(str(exc)) from exc