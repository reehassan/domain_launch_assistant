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
    DnsRecordCreateRequestSerializer,
    DnsRecordUpdateRequestSerializer,
    DomainCheckSerializer,
)
from domain_launch_assistant.dns.services.check_domain import (
    CheckDomainService,
    CheckDomainUnsupportedTypeError,
)
from domain_launch_assistant.dns.services.dns_records import (
    DnsRecordsError,
    DnsRecordsGuardError,
    DnsRecordsProviderError,
    DnsRecordsService,
    DnsRecordsTimeoutError,
)

from domain_launch_assistant.dns.tasks import (
    create_dns_record_task,
    delete_dns_record_task,
    run_domain_checks_task,
    update_dns_record_task,
)
from domain_launch_assistant.domains.models import DomainResult
from domain_launch_assistant.launches.models import LaunchProject
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
        expected_value = serializer.validated_data.get("expected_value")

        try:
            CheckDomainService.validate_check_types(check_types)
        except CheckDomainUnsupportedTypeError as exc:
            return api_error(
                code="VALIDATION_ERROR",
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Concurrency Lock Check
        if TaskRecord.has_active_task(project):
            return api_error(
                code="CONFLICT",
                message="A task is already in progress for this project. Please wait for it to finish.",
                status_code=status.HTTP_409_CONFLICT,
            )

        checks = CheckDomainService().create_pending_checks(
            project=project,
            domain_result=domain_result,
            check_types=check_types,
            expected_value=expected_value,
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


class DnsRecordListView(APIView):
    """
    List DNS records for a domain, live from name.com's sandbox — no
    local model, name.com is the only source of truth (see
    dns/services/dns_records.py for why this must hit the sandbox host,
    not production: the domain only exists there, since registration
    itself is sandbox-only — see registration_simulation.py).

    Synchronous, unlike every other name.com-backed endpoint in this
    app: there's no DomainCheck/DomainClaim-style row to read from the
    local DB instead, so this is a direct live proxy read. A slow or
    failed provider call here fails inline rather than as a TaskRecord
    failure.

    Gated on LaunchProject.status == READY, mirroring
    DomainRegistrationSimulateView's gate — the closest durable signal
    this app has for "this domain is far enough along to be pointed
    somewhere" (registration_simulation.py deliberately persists no
    "was this actually registered" flag).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, domain_id):
        domain_result = get_object_or_404(
            DomainResult,
            id=domain_id,
            project__user=request.user,
        )

        if domain_result.project.status != LaunchProject.Status.READY:
            return api_error(
                code="CONFLICT",
                message="DNS record management is only available once the project is READY.",
                status_code=status.HTTP_409_CONFLICT,
            )

        try:
            records = DnsRecordsService().list_records(domain_result)
        except DnsRecordsGuardError as exc:
            return api_error(
                code="INTERNAL_ERROR",
                message=str(exc),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except DnsRecordsTimeoutError:
            return api_error(
                code="EXTERNAL_API_TIMEOUT",
                message="The DNS provider did not respond. Please try again.",
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except DnsRecordsProviderError:
            return api_error(
                code="EXTERNAL_API_ERROR",
                message="DNS record lookup is temporarily unavailable.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"results": records})


class DnsRecordCreateView(APIView):
    """
    Kicks off DNS record creation as a background task — async like
    every other *mutating* name.com call in this app (check-claims/,
    simulate-registration/), even though a single Create Record call is
    typically fast; consistency with the rest of the app's polling
    pattern matters more here than shaving one round trip.

    Same READY gate as DnsRecordListView, for the same reason.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, domain_id):
        domain_result = get_object_or_404(
            DomainResult,
            id=domain_id,
            project__user=request.user,
        )

        if domain_result.project.status != LaunchProject.Status.READY:
            return api_error(
                code="CONFLICT",
                message="DNS record management is only available once the project is READY.",
                status_code=status.HTTP_409_CONFLICT,
            )

        serializer = DnsRecordCreateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="VALIDATION_ERROR",
                message="The request contains invalid data.",
                status_code=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )

        if TaskRecord.has_active_task(domain_result.project):
            return api_error(
                code="CONFLICT",
                message="A task is already in progress for this project. Please wait for it to finish.",
                status_code=status.HTTP_409_CONFLICT,
            )

        task_id = uuid.uuid4()
        TaskRecord.objects.create(
            task_id=task_id,
            project=domain_result.project,
            status=TaskRecord.Status.PENDING,
        )

        create_dns_record_task.delay(
            str(task_id),
            str(domain_result.id),
            serializer.validated_data,
        )

        return Response(
            {
                "domain_id": str(domain_result.id),
                "status": "PROCESSING",
                "task_id": str(task_id),
            },
            status=status.HTTP_202_ACCEPTED,
        )

class DnsRecordUpdateView(APIView):
    """
    Kicks off DNS record update as a background task — same async
    pattern as DnsRecordCreateView. name.com's UpdateRecord replaces
    the whole record, so the request body must supply the complete
    desired record, not just the changed field(s).
    Same READY gate as DnsRecordCreateView/DnsRecordListView.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, domain_id, record_id):
        domain_result = get_object_or_404(
            DomainResult,
            id=domain_id,
            project__user=request.user,
        )

        if domain_result.project.status != LaunchProject.Status.READY:
            return api_error(
                code="CONFLICT",
                message="DNS record management is only available once the project is READY.",
                status_code=status.HTTP_409_CONFLICT,
            )

        serializer = DnsRecordUpdateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="VALIDATION_ERROR",
                message="The request contains invalid data.",
                status_code=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )

        if TaskRecord.has_active_task(domain_result.project):
            return api_error(
                code="CONFLICT",
                message="A task is already in progress for this project. Please wait for it to finish.",
                status_code=status.HTTP_409_CONFLICT,
            )

        task_id = uuid.uuid4()
        TaskRecord.objects.create(
            task_id=task_id,
            project=domain_result.project,
            status=TaskRecord.Status.PENDING,
        )

        update_dns_record_task.delay(
            str(task_id),
            str(domain_result.id),
            record_id,
            serializer.validated_data,
        )

        return Response(
            {
                "domain_id": str(domain_result.id),
                "status": "PROCESSING",
                "task_id": str(task_id),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class DnsRecordDeleteView(APIView):
    """
    Kicks off DNS record deletion as a background task — same async
    pattern as DnsRecordCreateView/DnsRecordUpdateView. No request
    body: record_id in the URL is all name.com's DeleteRecord needs.
    Same READY gate as the other DNS record endpoints.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, domain_id, record_id):
        domain_result = get_object_or_404(
            DomainResult,
            id=domain_id,
            project__user=request.user,
        )

        if domain_result.project.status != LaunchProject.Status.READY:
            return api_error(
                code="CONFLICT",
                message="DNS record management is only available once the project is READY.",
                status_code=status.HTTP_409_CONFLICT,
            )

        if TaskRecord.has_active_task(domain_result.project):
            return api_error(
                code="CONFLICT",
                message="A task is already in progress for this project. Please wait for it to finish.",
                status_code=status.HTTP_409_CONFLICT,
            )

        task_id = uuid.uuid4()
        TaskRecord.objects.create(
            task_id=task_id,
            project=domain_result.project,
            status=TaskRecord.Status.PENDING,
        )

        delete_dns_record_task.delay(str(task_id), str(domain_result.id), record_id)

        return Response(
            {
                "domain_id": str(domain_result.id),
                "status": "PROCESSING",
                "task_id": str(task_id),
            },
            status=status.HTTP_202_ACCEPTED,
        )