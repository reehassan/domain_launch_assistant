# domain_launch_assistant/domains/services/availability.py

import re
from datetime import datetime, timezone

from domain_launch_assistant.domains.clients.namecom import NameComClient
from domain_launch_assistant.domains.models import DomainResult


class AvailabilityService:
    """
    Translates a brand name + list of extensions into normalized
    domain-availability dicts, ready to become DomainResult rows.

    Knows the DomainResult status vocabulary but not DomainSearch or
    any persistence — that orchestration lives in services/domain_search.py.
    """

    PROVIDER = "name.com"

    def __init__(self, namecom_client: NameComClient | None = None):
        self.namecom_client = namecom_client or NameComClient()

    def check_domains(self, brand_name: str, extensions: list[str]) -> list[dict]:
        """
        Raises NameComTimeoutError / NameComAPIError on provider failure
        (propagated unchanged from NameComClient) — a genuine provider
        outage must never reach the caller disguised as TAKEN results
        (api-contract.md section 28, rule #6).

        Raises ValueError if brand_name has no valid domain-label
        characters at all (e.g. all punctuation/emoji).
        """
        base_name = self._slugify(brand_name)
        domain_names = [f"{base_name}{ext}" for ext in extensions]

        raw_results = self.namecom_client.check_availability(domain_names)
        by_domain = {r["domainName"].lower(): r for r in raw_results}
        checked_at = datetime.now(timezone.utc)

        normalized = []
        for domain_name, ext in zip(domain_names, extensions):
            raw = by_domain.get(domain_name)

            if raw is None:
                # name.com's response omitted this specific domain even
                # though the request as a whole succeeded — a per-domain
                # failure, not a provider outage (that already raised above).
                normalized.append({
                    "domain": domain_name,
                    "extension": ext,
                    "available": False,
                    "status": DomainResult.Status.CHECK_FAILED,
                    "provider": self.PROVIDER,
                    "checked_at": checked_at,
                    "raw_metadata": None,
                })
                continue

            is_available = bool(raw.get("purchasable", False))
            normalized.append({
                "domain": domain_name,
                "extension": ext,
                "available": is_available,
                "status": (
                    DomainResult.Status.AVAILABLE
                    if is_available
                    else DomainResult.Status.TAKEN
                ),
                "provider": self.PROVIDER,
                "checked_at": checked_at,
                "raw_metadata": raw,
            })

        return normalized

    @staticmethod
    def _slugify(brand_name: str) -> str:
        """
        Reduces a brand name to a valid domain label: lowercase,
        alphanumerics only, no spaces or punctuation.
        e.g. "Ledger & Flow" -> "ledgerflow", "O'Domain" -> "odomain"
        """
        slug = re.sub(r"[^a-z0-9]", "", brand_name.strip().lower())
        if not slug:
            raise ValueError(
                f"Brand name '{brand_name}' has no valid characters for a domain label."
            )
        return slug