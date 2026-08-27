# domain_launch_assistant/domains/clients/namecom.py

import requests
from django.conf import settings

from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComTimeoutError,
)


class NameComClient:
    """
    Thin HTTP client for the name.com domain-availability API (Core API v1;
    the older v4 endpoint is deprecated).

    Knows nothing about Django models, DomainSearch, or DomainResult —
    it only translates between name.com's HTTP API and plain dicts,
    raising typed exceptions on failure. Application-level normalization
    happens in services/availability.py, services/domain_claims.py, and
    services/registration_simulation.py.
    """

    def __init__(
        self,
        username: str | None = None,
        token: str | None = None,
        base_url: str | None = None,
        timeout: int = 10,
    ):
        self.username = username or settings.NAMECOM_USERNAME
        self.token = token or settings.NAMECOM_API_TOKEN
        self.base_url = base_url or settings.NAMECOM_BASE_URL
        self.timeout = timeout

    def check_availability(self, domain_names: list[str]) -> list[dict]:
        """
        domain_names: full domain names, e.g. ["ledgerflow.com", "ledgerflow.ai"]

        Returns name.com's raw `results` list, e.g.:
            [{"domainName": "ledgerflow.com", "purchasable": False}, ...]

        Raises NameComTimeoutError / NameComAPIError on any provider
        failure. Callers must not interpret these as "domain taken" —
        they mean the check itself did not succeed.
        """
        url = f"{self.base_url}/domains:checkAvailability"

        try:
            response = requests.post(
                url,
                json={"domainNames": domain_names},
                auth=(self.username, self.token),
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise NameComTimeoutError("name.com did not respond in time.") from exc
        except requests.RequestException as exc:
            raise NameComAPIError(f"name.com request failed: {exc}") from exc

        if response.status_code >= 500:
            raise NameComAPIError(f"name.com returned server error {response.status_code}.")
        if response.status_code >= 400:
            raise NameComAPIError(
                f"name.com returned client error {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise NameComAPIError("name.com returned an unparseable response.") from exc

        results = data.get("results")
        if results is None:
            raise NameComAPIError("name.com response missing 'results'.")

        return results

    def get_domain_claims(self, domain_name: str) -> dict:
        """
        Calls POST /domaininfo/claims/{domain} — name.com's TMCH claims
        lookup. NOTE: this is a POST despite being a read/check operation
        (confirmed against docs.name.com's Check Domain Claims reference —
        name.com models it as "perform a claims check", not a GET lookup).

        Returns the raw response dict. Per name.com's documented shape,
        the "does this domain have a claim" signal is the top-level
        `claimId` (non-null when a claim exists) — NOT whether `claims`
        is non-empty. name.com's own "claims found" example response
        still shows `claims: []`, so callers (see domain_claims.py) must
        key off `claimId`, not list length:
            {
              "domain": "...", "claims": [...], "claimsProcessActive": bool,
              "claimId": str | None, "notBefore": str | None,
              "notAfter": str | None, "claimsNotice": str
            }

        Raises NameComTimeoutError / NameComAPIError on any provider
        failure. Callers must not interpret these as "no claims" — a
        failed check means we don't know, not that the domain is clear.
        """
        url = f"{self.base_url}/domaininfo/claims/{domain_name}"

        try:
            response = requests.post(
                url,
                json={"purchaseType": "registration"},
                auth=(self.username, self.token),
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise NameComTimeoutError("name.com did not respond in time.") from exc
        except requests.RequestException as exc:
            raise NameComAPIError(f"name.com request failed: {exc}") from exc

        if response.status_code >= 500:
            raise NameComAPIError(f"name.com returned server error {response.status_code}.")
        if response.status_code >= 400:
            raise NameComAPIError(
                f"name.com returned client error {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise NameComAPIError("name.com returned an unparseable response.") from exc

        if "claims" not in data:
            raise NameComAPIError("name.com response missing 'claims'.")

        return data

    def register_domain(
        self,
        domain_name: str,
        purchase_price,
        purchase_type: str,
        contact: dict,
        years: int = 1,
    ) -> dict:
        """
        Calls POST /domains — name.com's real Create Domain endpoint.
        Whether this registers in production or in the sandbox depends
        entirely on self.base_url; callers that need the sandbox-only
        guarantee must go through DomainRegistrationSimulationService,
        which refuses to construct a client at all unless self.base_url
        resolves to the sandbox host.

        `contact` must already be a fully-formed name.com contact dict
        (firstName, lastName, address1, city, state, zip, country, email,
        phone). It is reused for all four contact roles (registrant,
        admin, tech, billing) — matches name.com's documented v4 Create
        Domain payload shape, which Core v1 carries forward per its
        changelog (POST/PUT contact schemas require the same fields).

        purchase_price is cast to float before sending — DomainResult
        stores it as a Decimal, which is not JSON-serializable by
        `requests`' json= parameter.

        Returns the raw response dict (the created Domain object).
        ASSUMPTION — not verified against a real sandbox payload: Create
        Domain's exact response shape wasn't available in name.com's
        public docs at the time this was written. Callers should treat
        any field access beyond `domainName` defensively — see
        DomainRegistrationSimulationService's handling of `orderId`.

        Raises NameComTimeoutError / NameComAPIError on any provider
        failure, same discipline as the other methods on this client.
        """
        url = f"{self.base_url}/domains"

        payload = {
            "domain": {
                "domainName": domain_name,
                "contacts": {
                    "registrant": contact,
                    "admin": contact,
                    "tech": contact,
                    "billing": contact,
                },
            },
            "purchasePrice": float(purchase_price) if purchase_price is not None else None,
            "purchaseType": purchase_type,
            "years": years,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                auth=(self.username, self.token),
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise NameComTimeoutError("name.com did not respond in time.") from exc
        except requests.RequestException as exc:
            raise NameComAPIError(f"name.com request failed: {exc}") from exc

        if response.status_code >= 500:
            raise NameComAPIError(f"name.com returned server error {response.status_code}.")
        if response.status_code >= 400:
            raise NameComAPIError(
                f"name.com returned client error {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise NameComAPIError("name.com returned an unparseable response.") from exc

        return data