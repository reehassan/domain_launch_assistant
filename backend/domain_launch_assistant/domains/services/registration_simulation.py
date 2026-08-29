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
    Price handling: purchase_price is re-fetched from the sandbox
    client's own checkAvailability call immediately before registering
    — NOT read off the stored DomainResult. Sandbox and production
    name.com environments return different (test) prices for the same
    domain, so a price captured during the founder's real domain search
    (production) will be rejected by the sandbox's Create Domain
    endpoint with 400 "Purchase price does not match" if submitted
    as-is. This costs one extra provider round-trip per call but is the
    only price guaranteed to be valid for the environment actually being
    hit.
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
        base URL only. Price is re-fetched from THIS SAME sandbox client
        immediately before registering — sandbox and production return
        different (test) prices for the same domain, so the price
        originally stored on domain_result (from the production
        checkAvailability call that ran during the founder's actual
        domain search) can never be trusted here. Submitting a
        mismatched price is rejected by name.com with 400 "Purchase
        price does not match".
        Raises typed errors on any failure; callers (the Celery task)
        must not persist anything on failure — same discipline as
        DomainClaimsService.
        """
        try:
            availability = self.namecom_client.check_availability([domain_result.domain])
        except NameComTimeoutError as exc:
            raise DomainRegistrationSimulationTimeoutError(str(exc)) from exc
        except NameComAPIError as exc:
            raise DomainRegistrationSimulationProviderError(str(exc)) from exc

        # ASSUMPTION — not verified against every possible sandbox
        # response shape: check_availability is expected to return a
        # list with exactly one entry for a single-domain query (as
        # confirmed manually for kiply.dev). If the sandbox ever omits
        # the domain or returns it as unpurchasable, that's a real
        # failure state, not something to paper over with a fallback
        # price.
        if not availability or not availability[0].get("purchasable"):
            raise DomainRegistrationSimulationProviderError(
                f"Sandbox reports '{domain_result.domain}' is not purchasable."
            )
        sandbox_price = availability[0]["purchasePrice"]
        sandbox_purchase_type = availability[0].get("purchaseType") or "registration"

        try:
            raw = self.namecom_client.register_domain(
                domain_name=domain_result.domain,
                purchase_price=sandbox_price,
                purchase_type=sandbox_purchase_type,
                contact=self._demo_contact(),
            )
        except NameComTimeoutError as exc:
            raise DomainRegistrationSimulationTimeoutError(str(exc)) from exc
        except NameComAPIError as exc:
            raise DomainRegistrationSimulationProviderError(str(exc)) from exc
        # CONFIRMED against a real name.com sandbox response
        # (2026-08-29, verified manually against a live Create Domain
        # call): the created order's identifier is the top-level
        # integer field `order` — `orderId` does not appear anywhere
        # in the response and was always silently falling through to
        # the synthesized fallback below. Cast to str since this is a
        # display identifier, not something arithmetic is ever done
        # on. The synthesized fallback is kept for defense-in-depth
        # only (e.g. a future sandbox API version dropping the field)
        # — a missing display field must never fail an otherwise-
        # successful sandbox registration.
        order_id = (
            str(raw["order"])
            if raw.get("order") is not None
            else f"sandbox-{domain_result.domain}"
        )
        # CONFIRMED against the same live sandbox response used to
        # verify `order` above: privacyEnabled is a plain boolean
        # nested under the top-level `domain` object. Read here at
        # zero extra cost — no second provider call — since this
        # comes back on the exact same Create Domain response already
        # captured above.
        privacy_enabled = raw.get("domain", {}).get("privacyEnabled")
        return {
            "simulated": True,
            "order_id": order_id,
            "privacy_enabled": privacy_enabled,
            "message": "Registered in name.com sandbox — no real domain or charge.",
        }

    def toggle_privacy(self, domain_name: str, enabled: bool) -> dict:
        """
        Toggles WHOIS privacy for a domain already registered in the
        sandbox (via simulate_registration). Reuses this same
        instance's sandbox-only NameComClient — the constructor guard
        already refused to build at all unless NAMECOM_TEST_BASE_URL
        resolves to the sandbox host, so no second guard is needed
        here.

        Raises the same typed errors as simulate_registration, for the
        same reasons — including on a 409 from name.com, which per
        their docs specifically means this domain/TLD doesn't support
        WHOIS privacy, not a transient failure.
        """
        try:
            raw = self.namecom_client.update_domain_privacy(domain_name, enabled)
        except NameComTimeoutError as exc:
            raise DomainRegistrationSimulationTimeoutError(str(exc)) from exc
        except NameComAPIError as exc:
            raise DomainRegistrationSimulationProviderError(str(exc)) from exc

        return {
            "domain": raw.get("domainName", domain_name),
            "privacy_enabled": raw.get("privacyEnabled"),
            "message": "WHOIS privacy updated in name.com sandbox — no real domain affected.",
        }