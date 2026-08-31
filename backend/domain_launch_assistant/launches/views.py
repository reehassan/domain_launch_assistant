from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from domain_launch_assistant.brands.serializers import BrandIdeaSerializer
from domain_launch_assistant.dns.models import DomainCheck
from domain_launch_assistant.dns.serializers import DomainCheckSerializer
from domain_launch_assistant.domains.models import DomainClaim
from domain_launch_assistant.domains.serializers import (
    DomainClaimSerializer,
    DomainResultSerializer,
)

from .models import LaunchProject
from .serializers import LaunchProjectSerializer


class LaunchProjectViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Handles:
        POST /api/v1/projects/
        GET  /api/v1/projects/
        GET  /api/v1/projects/{id}/
    Only Create, List, and Retrieve for Day 1 — Update/Delete come later
    once there's an actual workflow that needs them.
    """

    serializer_class = LaunchProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # This is the ownership enforcement: a user can never see another
        # user's projects because they're never in the queryset to begin
        # with. Don't rely on serializer-level checks alone for this.
        #
        # ordered explicitly (-created_at) so pagination is stable —
        # Postgres doesn't guarantee row order without it.
        return LaunchProject.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class LaunchReportView(APIView):
    """
    Aggregates existing data into a single "what did this launch
    accomplish" summary — api-contract.md section 26. Pure read-only
    aggregation of the local database: no new Celery task, no new
    provider call, no TaskRecord. Reachable at any project status, not
    just READY, so a founder mid-flow sees partial progress instead of
    a 404.

    Deliberately excludes two things a naive reading of the contract's
    example might suggest:

      - DNS records: dns/views.py's DnsRecordListView is the one GET
        endpoint in this app that is NOT a local-DB read — it proxies
        name.com live on every call. Baking that into this endpoint
        would make "get the launch report" secretly also mean "make an
        external API call", which undercuts the whole point of this
        being a fast, always-safe summary. The frontend already has
        DomainDnsPanel.jsx hitting dns-records/ independently; it can
        render that alongside this report instead.

      - A registration receipt / "Registered: yes" flag: confirmed
        against registration_simulation.py + domains/tasks.py that
        simulate_registration_task's result is never persisted beyond
        TaskRecord (data-model.md section 9 deliberately keeps
        LaunchProject free of any "was this registered" column). This
        endpoint can only honestly report what the database actually
        knows — brand, domain, claims, checks — not a fact nothing
        ever wrote down.

    readiness.score is computed directly from DomainCheck rows (latest
    per check_type, same "read the newest row" convention used by
    claims/recommendations elsewhere in this app) — specifically the
    percentage of DOMAIN_READINESS-type checks that are PASS. No
    separate scoring service exists anywhere in this codebase, so this
    is the score, not a summary of some other computation.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        brand_data = (
            BrandIdeaSerializer(project.selected_brand).data
            if project.selected_brand
            else None
        )

        domain_data = (
            DomainResultSerializer(project.selected_domain).data
            if project.selected_domain
            else None
        )

        claim_data = None
        if project.selected_domain:
            latest_claim = (
                DomainClaim.objects.filter(domain_result=project.selected_domain)
                .order_by("-checked_at")
                .first()
            )
            if latest_claim is not None:
                claim_data = DomainClaimSerializer(latest_claim).data

        # Latest DomainCheck per check_type for the selected domain —
        # DomainCheck.Meta.ordering is already -created_at, so the
        # first row seen per check_type in this loop is the newest.
        latest_checks_by_type = {}
        if project.selected_domain:
            all_checks = DomainCheck.objects.filter(
                project=project,
                domain_result=project.selected_domain,
            )
            for check in all_checks:
                if check.check_type not in latest_checks_by_type:
                    latest_checks_by_type[check.check_type] = check

        checks_data = DomainCheckSerializer(
            list(latest_checks_by_type.values()), many=True
        ).data

        readiness_checks = [
            check
            for check in latest_checks_by_type.values()
            if check.check_type == DomainCheck.CheckType.DOMAIN_READINESS
        ]
        if readiness_checks:
            passed = sum(
                1 for c in readiness_checks if c.status == DomainCheck.Status.PASS
            )
            score = round(100 * passed / len(readiness_checks))
        else:
            score = 0

        blocking_issues = []
        if project.selected_brand is None:
            blocking_issues.append("No brand has been selected yet.")
        if project.selected_domain is None:
            blocking_issues.append("No domain has been selected yet.")
        if claim_data and claim_data["has_claims"]:
            blocking_issues.append("The selected domain has active trademark claims.")
        for check in readiness_checks:
            if check.status != DomainCheck.Status.PASS:
                blocking_issues.append(
                    check.message or "Domain readiness check has not passed."
                )
        if not readiness_checks and project.selected_domain is not None:
            blocking_issues.append("Domain readiness has not been checked yet.")

        ready = project.status == LaunchProject.Status.READY

        return Response(
            {
                "project": {
                    "id": str(project.id),
                    "name": project.name,
                    "status": project.status,
                },
                "brand": brand_data,
                "domain": domain_data,
                "claims": claim_data,
                "checks": checks_data,
                "readiness": {
                    "ready": ready,
                    "score": score,
                    "blocking_issues": blocking_issues,
                },
            },
            status=status.HTTP_200_OK,
        )