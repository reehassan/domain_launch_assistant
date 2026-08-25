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
from domain_launch_assistant.dns.tasks import run_domain_checks_task
from domain_launch_assistant.domains.models import DomainResult
from domain_launch_assistant.tasks.models import TaskRecord
from domain_launch_assistant.utils.exceptions import api_error


class CheckDomainView(APIView):
    """
    Kicks off DNS/domain readiness checks as a background task.
    Corresponds to api-contract.md section 20.
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

        check_types = serializer.validated_data["check_types"]

        try:
            CheckDomainService.validate_check_types(check_types)
        except CheckDomainUnsupportedTypeError as exc:
            return api_error(
                code="VALIDATION_ERROR",
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        checks = CheckDomainService().create_pending_checks(
            project=project,
            domain_result=domain_result,
            check_types=check_types,
        )

        task_id = uuid.uuid4()
        TaskRecord.objects.create(
            task_id=task_id,
            project=project,
            status=TaskRecord.Status.PENDING,
        )

        run_domain_checks_task.delay(str(task_id), [str(c.id) for c in checks])

        return Response(
            {
                "domain_id": str(domain_result.id),
                "status": "PROCESSING",
                "task_id": str(task_id),
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