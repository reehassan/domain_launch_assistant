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
    happens in services/availability.py and services/domain_claims.py.
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