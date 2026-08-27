# domain_launch_assistant/domains/services/registration_simulation.py

from urllib.parse import urlparse

from django.conf import settings

from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComSandboxGuardError,
    NameComTimeoutError,
)
from domain_launch_assistant.domains.clients.namecom import NameComClient
from domain_launch_assistant.domains.models import DomainResult


class DomainRegistrationSimulationError(Exception):
    pass


class DomainRegistrationSimulationTimeoutError(DomainRegistrationSimulationError):
    """The provider did not respond in time. Maps to EXTERNAL_API_TIMEOUT."""
    pass


class DomainRegistrationSimulationProviderError(DomainRegistrationSimulationError):
    """The provider responded with an error. Maps to EXTERNAL_API_ERROR."""
    pass


class DomainRegistrationSimulationGuardError(DomainRegistrationSimulationError):
    """
    The sandbox base-url guard refused to run. Must never be treated as a
    routine provider failure — it means the app is configured in a way
    that could otherwise let a "sandbox" call hit production. Maps to
    INTERNAL_ERROR, not EXTERNAL_API_ERROR.
    """
    pass


class DomainRegistrationSimulationService:
    """
    Sandbox-only "Simulate Registration" demo action (api-contract.md
    section 24). Constructs its OWN NameComClient from NAMECOM_TEST_*
    settings — never the production client instance used by
    AvailabilityService / DomainClaimsService (architecture.md sections
    10, 19).

    Hard guard: refuses to build a client at all if NAMECOM_TEST_BASE_URL
    does not resolve to the sandbox host. This is the actual safety
    mechanism — a shared client instance is exactly how a "sandbox" call
    would end up hitting production — so the check runs before any HTTP
    call, and before the client object even exists.

    Persists nothing itself: the outcome is written by the caller (the
    Celery task) through TaskRecord only. No new model, no
    LaunchProject.status transition (data-model.md section 9).
    """

    
    def __init__(self, namecom_client: NameComClient | None = None):
        try:
            if namecom_client is not None:
                # Test-only escape hatch for injecting a pre-built client —
                # still runs through the same guard via its base_url, so a
                # caller can't bypass the safety check by constructing its
                # own client and handing it in.
                self._guard_base_url(namecom_client.base_url)
                self.namecom_client = namecom_client
            else:
                self.namecom_client = self._build_sandbox_client()
        except NameComSandboxGuardError as exc:
            raise DomainRegistrationSimulationGuardError(str(exc)) from exc

    @staticmethod
    def _guard_base_url(base_url: str) -> None:
        host = urlparse(base_url).hostname or ""
        if host != settings.NAMECOM_SANDBOX_HOST:
            raise NameComSandboxGuardError(
                f"Refusing to simulate registration: configured base URL "
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

    @staticmethod
    def _demo_contact() -> dict:
        """
        Fixed placeholder registrant used for every sandbox call — not
        tied to the founder's account, never persisted. See settings
        NAMECOM_TEST_CONTACT_* (config/settings/base.py).
        """
        return {
            "firstName": settings.NAMECOM_TEST_CONTACT_FIRST_NAME,
            "lastName": settings.NAMECOM_TEST_CONTACT_LAST_NAME,
            "address1": settings.NAMECOM_TEST_CONTACT_ADDRESS1,
            "city": settings.NAMECOM_TEST_CONTACT_CITY,
            "state": settings.NAMECOM_TEST_CONTACT_STATE,
            "zip": settings.NAMECOM_TEST_CONTACT_ZIP,
            "country": settings.NAMECOM_TEST_CONTACT_COUNTRY,
            "email": settings.NAMECOM_TEST_CONTACT_EMAIL,
            "phone": settings.NAMECOM_TEST_CONTACT_PHONE,
        }

    def simulate_registration(self, domain_result: DomainResult) -> dict:
        """
        Calls name.com's real Create Domain endpoint against the sandbox
        base URL only, using purchase_price/purchase_type already stored
        on domain_result (from the original checkAvailability call — no
        extra provider round-trip to re-price).

        Raises typed errors on any failure; callers (the Celery task)
        must not persist anything on failure — same discipline as
        DomainClaimsService.
        """
        try:
            raw = self.namecom_client.register_domain(
                domain_name=domain_result.domain,
                purchase_price=domain_result.purchase_price,
                purchase_type=domain_result.purchase_type or "registration",
                contact=self._demo_contact(),
            )
        except NameComTimeoutError as exc:
            raise DomainRegistrationSimulationTimeoutError(str(exc)) from exc
        except NameComAPIError as exc:
            raise DomainRegistrationSimulationProviderError(str(exc)) from exc

        # ASSUMPTION — not verified against a real sandbox payload: Create
        # Domain's exact response shape wasn't available in name.com's
        # public docs when this was written. `orderId` is name.com's
        # documented field for order identifiers elsewhere in the API
        # (List/Get Order), so it's used here if present. If the sandbox
        # response omits it, a synthesized identifier is used instead —
        # a missing display field must never fail an otherwise-successful
        # sandbox registration.
        order_id = raw.get("orderId") or f"sandbox-{domain_result.domain}"

        return {
            "simulated": True,
            "order_id": order_id,
            "message": "Registered in name.com sandbox — no real domain or charge.",
        }