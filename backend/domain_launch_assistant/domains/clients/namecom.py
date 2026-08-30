# domain_launch_assistant/domains/clients/namecom.py

import time

import requests
from django.conf import settings

from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComClientError,
    NameComTimeoutError,
)


class NameComClient:
    """
    Thin HTTP client for the name.com domain-availability API (Core API v1;
    the older v4 endpoint is deprecated).

    Knows nothing about Django models, DomainSearch, or DomainResult —
    it only translates between name.com's HTTP API and plain dicts,
    raising typed exceptions on failure. Application-level normalization
    happens in services/availability.py, services/domain_claims.py,
    services/registration_simulation.py, and services/dns_records.py.
    """

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_BACKOFF_BASE = 0.5

    def __init__(
        self,
        username: str | None = None,
        token: str | None = None,
        base_url: str | None = None,
        timeout: int = 10,
        max_retries: int | None = None,
        retry_backoff_base: float | None = None,
    ):
        self.username = username or settings.NAMECOM_USERNAME
        self.token = token or settings.NAMECOM_API_TOKEN
        self.base_url = base_url or settings.NAMECOM_BASE_URL
        self.timeout = timeout
        self.max_retries = (
            max_retries
            if max_retries is not None
            else getattr(settings, "NAMECOM_MAX_RETRIES", self.DEFAULT_MAX_RETRIES)
        )
        self.retry_backoff_base = (
            retry_backoff_base
            if retry_backoff_base is not None
            else getattr(
                settings, "NAMECOM_RETRY_BACKOFF_BASE", self.DEFAULT_RETRY_BACKOFF_BASE
            )
        )

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Executes a single HTTP request with retry + exponential backoff,
        used by every method on this client instead of each duplicating
        its own try/except + status handling.

        Retries ONLY on:
          - requests.Timeout (name.com didn't respond in time)
          - HTTP 5xx (name.com's own server error)

        Never retries on 4xx — those are real validation errors (bad
        domain name, bad auth, bad payload) and retrying them would just
        waste calls and delay a response the caller can already act on.
        Never retries on other requests.RequestException (e.g. DNS/
        connection failures) either — same discipline as before this
        method existed, since those aren't the "throttle/transient"
        cases this wrapper targets.

        Attempts self.max_retries times total, sleeping
        `retry_backoff_base * 2 ** attempt` seconds between attempts
        (e.g. with the default base of 0.5s: 0.5s, then 1.0s). Raises
        the last-seen NameComTimeoutError/NameComAPIError once attempts
        are exhausted.
        """
        last_exc: NameComClientError | None = None

        for attempt in range(self.max_retries):
            try:
                response = requests.request(method, url, timeout=self.timeout, **kwargs)
            except requests.Timeout as exc:
                last_exc = NameComTimeoutError("name.com did not respond in time.")
                last_exc.__cause__ = exc
            except requests.RequestException as exc:
                raise NameComAPIError(f"name.com request failed: {exc}") from exc
            else:
                if response.status_code < 500:
                    return response
                last_exc = NameComAPIError(
                    f"name.com returned server error {response.status_code}."
                )

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_backoff_base * (2**attempt))

        raise last_exc

    def check_availability(self, domain_names: list[str]) -> list[dict]:
        """
        domain_names: full domain names, e.g. ["ledgerflow.com", "ledgerflow.ai"]

        Returns name.com's raw `results` list, e.g.:
            [{"domainName": "ledgerflow.com", "purchasable": False}, ...]

        Raises NameComTimeoutError / NameComAPIError on any provider
        failure. Callers must not interpret these as "domain taken" —
        they mean the check itself did not succeed. Timeouts and 5xx
        are retried with backoff before raising (see
        _request_with_retry); a 4xx raises immediately.
        """
        url = f"{self.base_url}/domains:checkAvailability"

        response = self._request_with_retry(
            "POST",
            url,
            json={"domainNames": domain_names},
            auth=(self.username, self.token),
        )

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
        Timeouts and 5xx are retried with backoff before raising (see
        _request_with_retry); a 4xx raises immediately.
        """
        url = f"{self.base_url}/domaininfo/claims/{domain_name}"

        response = self._request_with_retry(
            "POST",
            url,
            json={"purchaseType": "registration"},
            auth=(self.username, self.token),
        )

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
        CONFIRMED against a real name.com sandbox response (2026-08-29):
        the created order's identifier is the top-level integer field
        `order` (e.g. 2132074) — NOT `orderId`. There is no `orderId`
        field anywhere in the payload. The domain's own data lives
        nested under `domain` (domainName, createDate, expireDate,
        nameservers, etc.), and `totalPaid` is a top-level sibling of
        `order`. See DomainRegistrationSimulationService's handling of
        `order`.

        Raises NameComTimeoutError / NameComAPIError on any provider
        failure, same discipline as the other methods on this client.
        Timeouts and 5xx are retried with backoff before raising (see
        _request_with_retry); a 4xx raises immediately.
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

        response = self._request_with_retry(
            "POST",
            url,
            json=payload,
            auth=(self.username, self.token),
        )

        if response.status_code >= 400:
            raise NameComAPIError(
                f"name.com returned client error {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise NameComAPIError("name.com returned an unparseable response.") from exc

        return data

    def list_records(self, domain_name: str) -> list[dict]:
        """
        Calls GET /domains/{domainName}/records — name.com's List
        Records endpoint (Core API v1; confirmed against
        docs.name.com's DNS reference). Returns name.com's raw
        `records` list, each shaped like:
            {"id": int, "domainName": str, "host": str|None,
             "fqdn": str, "type": str, "answer": str,
             "ttl": int, "priority": int|None}

        Does not paginate: this app only ever expects a handful of
        records on a freshly-sandbox-registered domain, so a single
        unpaginated page (name.com's default perPage=1000) is enough —
        no nextPage/lastPage handling.

        Raises NameComTimeoutError / NameComAPIError on any provider
        failure, same discipline as check_availability/get_domain_claims.
        Timeouts and 5xx are retried with backoff before raising (see
        _request_with_retry); a 4xx raises immediately.
        """
        url = f"{self.base_url}/domains/{domain_name}/records"

        response = self._request_with_retry(
            "GET",
            url,
            auth=(self.username, self.token),
        )

        if response.status_code >= 400:
            raise NameComAPIError(
                f"name.com returned client error {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise NameComAPIError("name.com returned an unparseable response.") from exc

        return data.get("records", [])

    def create_record(
        self,
        domain_name: str,
        host: str,
        record_type: str,
        answer: str,
        ttl: int = 300,
        priority: int | None = None,
    ) -> dict:
        """
        Calls POST /domains/{domainName}/records — name.com's Create
        Record endpoint (Core API v1; confirmed against docs.name.com's
        DNS reference). `host` uses "" or "@" for an apex record.
        `priority` is only meaningful for MX/SRV records — name.com
        ignores it for every other type, so it's safe to omit for
        A/CNAME/etc.

        Returns the raw created Record dict, e.g.:
            {"id": 12345, "domainName": "example.org", "host": "www",
             "fqdn": "www.example.org.", "type": "A",
             "answer": "10.0.0.1", "ttl": 300, "priority": None}

        Raises NameComTimeoutError / NameComAPIError on any provider
        failure, same discipline as the other methods on this client.
        Timeouts and 5xx are retried with backoff before raising (see
        _request_with_retry); a 4xx raises immediately.
        """
        url = f"{self.base_url}/domains/{domain_name}/records"

        payload = {
            "host": host,
            "type": record_type,
            "answer": answer,
            "ttl": ttl,
        }
        if priority is not None:
            payload["priority"] = priority

        response = self._request_with_retry(
            "POST",
            url,
            json=payload,
            auth=(self.username, self.token),
        )

        if response.status_code >= 400:
            raise NameComAPIError(
                f"name.com returned client error {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise NameComAPIError("name.com returned an unparseable response.") from exc

        return data

    def update_record(
        self,
        domain_name: str,
        record_id: int,
        host: str,
        record_type: str,
        answer: str,
        ttl: int = 300,
        priority: int | None = None,
    ) -> dict:
        """
        Calls PUT /domains/{domainName}/records/{id} — name.com's Update
        Record endpoint (Core API v1; the v4 reference at
        docs.name.com's DNS page describes the same operation and path
        shape, consistent with this client's other endpoints already
        confirmed to carry forward unchanged into Core v1). Per
        name.com's docs: "UpdateRecord replaces the record with the new
        record that is passed" — this is a full replace, not a partial
        patch, so callers must supply the complete desired record
        (host/type/answer/ttl/priority), same field set as
        create_record.
        Returns the raw updated Record dict, same shape as
        create_record's return value.
        Raises NameComTimeoutError / NameComAPIError on any provider
        failure, same discipline as the other methods on this client.
        Timeouts and 5xx are retried with backoff before raising (see
        _request_with_retry); a 4xx raises immediately.
        """
        url = f"{self.base_url}/domains/{domain_name}/records/{record_id}"
        payload = {
            "host": host,
            "type": record_type,
            "answer": answer,
            "ttl": ttl,
        }
        if priority is not None:
            payload["priority"] = priority
        response = self._request_with_retry(
            "PUT",
            url,
            json=payload,
            auth=(self.username, self.token),
        )
        if response.status_code >= 400:
            raise NameComAPIError(
                f"name.com returned client error {response.status_code}: {response.text}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise NameComAPIError("name.com returned an unparseable response.") from exc
        return data

    def delete_record(self, domain_name: str, record_id: int) -> None:
        """
        Calls DELETE /domains/{domainName}/records/{id} — name.com's
        Delete Record endpoint (Core API v1; same v4-to-Core-v1
        carryover reasoning as update_record above). Per name.com's
        docs, a successful delete returns an empty response body — this
        method deliberately does NOT call response.json() on success
        (unlike every other method on this client), since there is
        nothing to parse and doing so would raise a spurious
        NameComAPIError on a call that actually succeeded.
        Returns None. Raises NameComTimeoutError / NameComAPIError on
        any provider failure, same discipline as the other methods on
        this client. Timeouts and 5xx are retried with backoff before
        raising (see _request_with_retry); a 4xx raises immediately
        (per name.com's docs, a record id that doesn't exist in the
        specified domain is one such error).
        """
        url = f"{self.base_url}/domains/{domain_name}/records/{record_id}"
        response = self._request_with_retry(
            "DELETE",
            url,
            auth=(self.username, self.token),
        )
        if response.status_code >= 400:
            raise NameComAPIError(
                f"name.com returned client error {response.status_code}: {response.text}"
            )
        return None

    def update_domain_privacy(self, domain_name: str, enabled: bool) -> dict:
        """
        Calls PATCH /domains/{domainName} — name.com's Update a Domain
        endpoint (Core API v1; confirmed against docs.name.com's
        Domains reference), scoped here to just the privacyEnabled
        field. The real endpoint also accepts autorenewEnabled and
        locked in the same PATCH body, but this app only ever toggles
        privacy, so those are intentionally omitted rather than
        exposed as unused parameters.

        Returns the raw updated Domain object, e.g.:
            {"domainName": "...", "privacyEnabled": bool,
             "autorenewEnabled": bool, "locked": bool,
             "contacts": {...}, "nameservers": [...], ...}

        Raises NameComTimeoutError / NameComAPIError on any provider
        failure. A 409 specifically means this domain/TLD doesn't
        support WHOIS privacy (per name.com's docs) — that's real,
        actionable information for the caller, not a transient
        failure, so it's surfaced as a plain NameComAPIError like any
        other 4xx rather than retried. Timeouts and 5xx are retried
        with backoff before raising (see _request_with_retry).
        """
        url = f"{self.base_url}/domains/{domain_name}"

        response = self._request_with_retry(
            "PATCH",
            url,
            json={"privacyEnabled": enabled},
            auth=(self.username, self.token),
        )

        if response.status_code >= 400:
            raise NameComAPIError(
                f"name.com returned client error {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise NameComAPIError("name.com returned an unparseable response.") from exc

        return data