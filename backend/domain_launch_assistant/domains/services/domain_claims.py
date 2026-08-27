# domain_launch_assistant/domains/services/domain_claims.py

from django.utils import timezone

from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComTimeoutError,
)
from domain_launch_assistant.domains.clients.namecom import NameComClient
from domain_launch_assistant.domains.models import DomainClaim, DomainResult


class DomainClaimsError(Exception):
    pass


class DomainClaimsTimeoutError(DomainClaimsError):
    """The provider did not respond in time. Maps to EXTERNAL_API_TIMEOUT."""
    pass


class DomainClaimsProviderError(DomainClaimsError):
    """The provider responded with an error. Maps to EXTERNAL_API_ERROR."""
    pass


class DomainClaimsService:
    """
    Runs an on-demand TMCH trademark-claims check for a single
    DomainResult, through the existing production NameComClient.

    A DomainClaim row is only ever created after a successful provider
    response — check_claims() never catches NameComTimeoutError /
    NameComAPIError to produce a "no claims" fallback. On failure it
    re-raises as a typed error and persists nothing, so a provider
    outage can never be mistaken for a clean trademark result.
    """

    def __init__(self, namecom_client: NameComClient | None = None):
        self.namecom_client = namecom_client or NameComClient()

    def check_claims(self, domain_result: DomainResult) -> DomainClaim:
        try:
            raw = self.namecom_client.get_domain_claims(domain_result.domain)
        except NameComTimeoutError as exc:
            raise DomainClaimsTimeoutError(str(exc)) from exc
        except NameComAPIError as exc:
            raise DomainClaimsProviderError(str(exc)) from exc

        # Per name.com's documented response (docs.name.com — Check Domain
        # Claims), `claims` can be an empty list even when a claim exists —
        # their own "claims found" example returns claims: []. The
        # authoritative signal is the top-level claimId: non-null means
        # TMCH has an active claim on this label, null means it doesn't.
        has_claims = raw.get("claimId") is not None

        return DomainClaim.objects.create(
            domain_result=domain_result,
            has_claims=has_claims,
            claims_data=raw,
            checked_at=timezone.now(),
        )