# domain_launch_assistant/dns/views.py

import uuid

from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from domain_launch_assistant.dns.models import DomainCheck
from domain_launch_assistant.dns.serializers import (
    CheckDomainRequestSerializer,
    DomainCheckSerializer,
)
from domain_launch_assistant.dns.services.check_domain import (
    CheckDomainService,
    CheckDomainUnsupportedTypeError,
)
from domain_launch_assistant.domains.models import DomainResult
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.utils.exceptions import api_error


class CheckDomainView(APIView):
    """
    Run DNS/domain readiness checks against a project's selected
    domain result.

    Corresponds to api-contract.md section 20. Note the URL lives
    under /domains/{id}/... per the contract's explicit call-out —
    {id} here is a DomainResult.id, not scoped through a project_id
    in the URL, so ownership is enforced via domain_result.project.user.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, domain_id):
        domain_result = get_object_or_404(
            DomainResult,
            id=domain_id,
            project__user=request.user,
        )
        project = domain_result.project

        serializer = CheckDomainRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="VALIDATION_ERROR",
                message="The request contains invalid data.",
                status_code=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )

        try:
            CheckDomainService().run_checks(
                project=project,
                domain_result=domain_result,
                check_types=serializer.validated_data["check_types"],
            )
        except CheckDomainUnsupportedTypeError as exc:
            return api_error(
                code="VALIDATION_ERROR",
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        project.status = LaunchProject.Status.VERIFYING_DNS
        project.save(update_fields=["status"])

        return Response(
            {
                "domain_id": str(domain_result.id),
                # Synchronous today, same placeholder pattern as
                # DomainSearchStartView — checks have actually already
                # run and been persisted by the time this responds, so
                # "COMPLETED" reflects real state rather than the
                # "PENDING" shown in api-contract.md's async example.
                # Revisit alongside domain_search.py once Celery is
                # wired into both.
                "status": "COMPLETED",
                "task_id": str(uuid.uuid4()),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class DomainCheckListView(APIView):
    """
    List domain checks for a domain result.
    Corresponds to api-contract.md section 21.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, domain_id):
        domain_result = get_object_or_404(
            DomainResult,
            id=domain_id,
            project__user=request.user,
        )

        checks = DomainCheck.objects.filter(
            domain_result=domain_result,
        ).order_by("-checked_at")

        serializer = DomainCheckSerializer(checks, many=True)
        return Response({"results": serializer.data})