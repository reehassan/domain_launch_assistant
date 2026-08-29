# domain_launch_assistant/domains/views.py

# Standard Library
import uuid

# Django
from django.conf import settings
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone

# Django REST Framework
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# Local Project App Imports
from domain_launch_assistant.brands.models import BrandIdea
from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComTimeoutError,
)
from domain_launch_assistant.domains.models import (
    DomainClaim,
    DomainRecommendation,
    DomainResult,
    DomainSearch,
)
from domain_launch_assistant.domains.serializers import (
    DomainClaimSerializer,
    DomainRecommendationSerializer,
    DomainResultSerializer,
    DomainSearchRequestSerializer,
    DomainSearchSerializer,
    SelectDomainSerializer,
    TogglePrivacySerializer,
)
from domain_launch_assistant.domains.services.domain_search import (
    DomainSearchError,
    DomainSearchInputError,
    DomainSearchProviderError,
    DomainSearchService,
    DomainSearchTimeoutError,
)
from domain_launch_assistant.domains.tasks import (
    check_domain_claims_task,
    check_domains_task,
    recommend_domain_task,
    simulate_registration_task,
    toggle_domain_privacy_task,
)
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.tasks.models import TaskRecord
from domain_launch_assistant.utils.exceptions import api_error



class DomainSearchStartView(APIView):
    """
    Start a domain availability search for a launch project, scoped to
    one of its brand ideas. Creates a PENDING DomainSearch row
    synchronously, then dispatches the actual provider check to a
    background task.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        serializer = DomainSearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="VALIDATION_ERROR",
                message="The request contains invalid data.",
                status_code=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )

        brand_idea = get_object_or_404(
            BrandIdea,
            id=serializer.validated_data["brand_idea_id"],
            project=project,
        )

        if TaskRecord.has_active_task(project):
            return api_error(
                code="CONFLICT",
                message="A task is already in progress for this project. Please wait for it to finish.",
                status_code=status.HTTP_409_CONFLICT,
            )

        search = DomainSearchService().create_pending_search(
            project=project,
            brand_idea=brand_idea,
            extensions=serializer.validated_data["extensions"],
        )

        task_id = uuid.uuid4()
        TaskRecord.objects.create(
            task_id=task_id,
            project=project,
            status=TaskRecord.Status.PENDING,
        )

        check_domains_task.delay(str(task_id), str(search.id))

        return Response(
            {
                "search_id": str(search.id),
                "project_id": str(project.id),
                # Hardcoded, not read from `search.status` — with
                # CELERY_TASK_ALWAYS_EAGER=True the task has already run
                # against a separate DB-fetched copy of this row by the
                # time we get here, so the local `search` object is
                # stale in tests even though it's accurate in production.
                "status": "PROCESSING",
                "task_id": str(task_id),
            },
            status=status.HTTP_202_ACCEPTED,
        )

class DomainSearchListView(APIView):
    """
    List domain searches for a launch project.
    Corresponds to api-contract.md section 16.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        searches = DomainSearch.objects.filter(
            project=project,
        ).order_by("-created_at")

        serializer = DomainSearchSerializer(searches, many=True)
        return Response({"results": serializer.data})


class DomainResultListView(APIView):
    """
    List domain results for a launch project, with optional filters.
    Corresponds to api-contract.md section 17.

    Query params: ?available=true|false, ?extension=.com, ?search=ledger

    Scoped to the project's latest COMPLETED DomainSearch only (audit
    fix — Ticket 1). Previously this queried DomainResult by `project`
    across every DomainSearch ever run for it, so regenerating a
    search (same brand_idea_id/extensions, a new DomainSearch row)
    left every prior search's results still showing up here alongside
    the new ones. DomainStep.jsx masks this within a single session by
    swapping its local state to just the new search's task result, but
    a page reload re-fetches this endpoint directly and the stale
    duplicates reappeared.
    
    Deliberately a read-side fix rather than deleting old
    DomainSearch/DomainResult rows on regenerate: DomainCheck,
    DomainClaim, and DomainRecommendation all point at DomainResult
    with on_delete=PROTECT, so deleting a prior search whose domains
    had already been checked/claimed/recommended would raise
    ProtectedError and crash the regenerate action outright. This way
    nothing is ever deleted — old rows stay in the DB, still directly
    reachable by ID (existing checks/claims/recommendations keep
    working) — they just stop appearing in *this* list once a newer
    search completes. If no DomainSearch has completed yet for the
    project, this correctly returns an empty result set rather than
    falling back to an in-progress/failed search's (nonexistent)
    results.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        latest_search = (
            DomainSearch.objects.filter(
                project=project,
                status=DomainSearch.Status.COMPLETED,
            )
            .order_by("-created_at")
            .first()
        )

        if latest_search is None:
            results = DomainResult.objects.none()
        else:
            results = DomainResult.objects.filter(search=latest_search)

        available_param = request.query_params.get("available")
        if available_param is not None:
            results = results.filter(
                available=available_param.lower() == "true"
            )

        extension_param = request.query_params.get("extension")
        if extension_param:
            results = results.filter(extension=extension_param)

        search_param = request.query_params.get("search")
        if search_param:
            results = results.filter(domain__icontains=search_param)

        results = results.order_by("-checked_at")

        serializer = DomainResultSerializer(results, many=True)
        return Response({"results": serializer.data})


class DomainSelectView(APIView):
    """
    Select an available domain for a launch project.
    Corresponds to api-contract.md section 18.

    Enforces api-contract.md section 28 rules:
      #4 Only available domains can be selected.
      #5 Stale domain availability must be refreshed before selection.
      #6 A domain with an active trademark claim cannot be selected
         (Ticket 6). This is a server-side backstop, not the primary
         UX: DomainClaimsCheck now runs automatically as soon as a
         domain card mounts (frontend), and DomainStep withholds the
         "Select" button until that check resolves to CLEAR. This
         check exists so the same rule holds for a direct API call
         that bypasses the frontend entirely, not just the UI gate.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        serializer = SelectDomainSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="VALIDATION_ERROR",
                message="The request contains invalid data.",
                status_code=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )

        domain_result = get_object_or_404(
            DomainResult,
            id=serializer.validated_data["domain_id"],
            project=project,
        )

        # Rule #4 — only available domains can be selected.
        if domain_result.status != DomainResult.Status.AVAILABLE:
            return api_error(
                code="CONFLICT",
                message="Only available domains can be selected.",
                status_code=status.HTTP_409_CONFLICT,
            )

        # Rule #5 — stale availability must be refreshed before selection.
        age = timezone.now() - domain_result.checked_at
        if age.total_seconds() > settings.DOMAIN_FRESHNESS_THRESHOLD_SECONDS:
            return api_error(
                code="CONFLICT",
                message="Domain availability is stale and must be refreshed before selection.",
                status_code=status.HTTP_409_CONFLICT,
            )

        # Rule #6 — a domain with an active trademark claim cannot be
        # selected. DomainClaim is append-only (Meta.ordering =
        # ["-checked_at"]), so the latest row is this domain's current
        # verdict. No claim on record yet is treated as not-blocking
        # here — the frontend now always runs a check before Select
        # ever renders, so in practice a claim row will already exist
        # by the time this is reachable through the UI; this guard's
        # job is only to make a claimed domain unselectable, not to
        # additionally mandate that a check has run at all.
        latest_claim = (
            DomainClaim.objects.filter(domain_result=domain_result)
            .order_by("-checked_at")
            .first()
        )
        if latest_claim is not None and latest_claim.has_claims:
            return api_error(
                code="CONFLICT",
                message="This domain has active trademark claims and cannot be selected.",
                status_code=status.HTTP_409_CONFLICT,
            )

        project.selected_domain = domain_result
        project.status = LaunchProject.Status.DOMAIN_SELECTED
        project.save(update_fields=["selected_domain", "status"])

        return Response(
            {
                "project_id": str(project.id),
                "selected_domain": DomainResultSerializer(domain_result).data,
                "status": project.status,
            }
        )


class DomainRecommendGenerateView(APIView):
    """
    Kicks off AI domain recommendation as a background task.
    Validation that doesn't need Gemini (a search has completed, at
    least one AVAILABLE domain exists) happens synchronously here —
    only the Gemini call and persistence step move into
    recommend_domain_task.

    Errors:
      409 — no domain search has completed for this project yet (a
            PENDING/PROCESSING/FAILED search does not satisfy this —
            audit fix, Ticket 9: previously this only checked that
            *some* DomainSearch row existed, so an in-progress or
            failed search slipped past here and was instead reported
            as the less accurate 400 below).
      400 — a completed search exists but no AVAILABLE domains to
            recommend from.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        if not DomainSearch.objects.filter(
            project=project,
            status=DomainSearch.Status.COMPLETED,
        ).exists():
            return api_error(
                code="CONFLICT",
                message="No domain search has been completed for this project yet.",
                status_code=status.HTTP_409_CONFLICT,
            )

        has_available = DomainResult.objects.filter(
            project=project,
            status=DomainResult.Status.AVAILABLE,
        ).exists()
        if not has_available:
            return api_error(
                code="VALIDATION_ERROR",
                message="No available domains to recommend from yet.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if TaskRecord.has_active_task(project):
            return api_error(
                code="CONFLICT",
                message="A task is already in progress for this project. Please wait for it to finish.",
                status_code=status.HTTP_409_CONFLICT,
            )

        task_id = uuid.uuid4()
        TaskRecord.objects.create(
            task_id=task_id,
            project=project,
            status=TaskRecord.Status.PENDING,
        )

        recommend_domain_task.delay(str(task_id), str(project.id))

        return Response(
            {"task_id": str(task_id), "status": "PROCESSING"},
            status=status.HTTP_202_ACCEPTED,
        )


class DomainRecommendationListView(APIView):
    """
    List AI domain recommendations for a project, newest first.
    Frontend reads the first entry (latest by created_at) for the
    "We'd pick X because Y" panel — same read pattern as brands/searches.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        recommendations = DomainRecommendation.objects.filter(
            project=project,
        ).order_by("-created_at")

        serializer = DomainRecommendationSerializer(recommendations, many=True)
        return Response({"results": serializer.data})


class DomainClaimsCheckView(APIView):
    """
    Kicks off an on-demand TMCH trademark-claims check for a single
    domain result, as a background task. Ownership is enforced via
    domain_result.project.user, since this endpoint hangs off
    /domains/{id}/, not /projects/{id}/... — same pattern dns/views.py
    already uses for CheckDomainView.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, domain_id):
        domain_result = get_object_or_404(
            DomainResult,
            id=domain_id,
            project__user=request.user,
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

        check_domain_claims_task.delay(str(task_id), str(domain_result.id))

        return Response(
            {
                "domain_id": str(domain_result.id),
                "status": "PROCESSING",
                "task_id": str(task_id),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class DomainClaimListView(APIView):
    """
    List trademark claim checks for a domain result, newest first.
    Same read pattern as DomainCheckListView in the dns app — frontend
    reads the first entry (latest by checked_at) for the "has claims"
    panel.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, domain_id):
        domain_result = get_object_or_404(
            DomainResult,
            id=domain_id,
            project__user=request.user,
        )

        claims = DomainClaim.objects.filter(
            domain_result=domain_result,
        ).order_by("-checked_at")

        serializer = DomainClaimSerializer(claims, many=True)
        return Response({"results": serializer.data})


class DomainRegistrationSimulateView(APIView):
    """
    Kicks off the sandbox-only "Simulate Registration" demo action as a
    background task. Ownership is enforced via domain_result.project.user,
    same pattern as DomainClaimsCheckView — this endpoint hangs off
    /domains/{id}/, not /projects/{id}/....

    Gated on LaunchProject.status == READY (api-contract.md section 24):
    the founder's project must have already passed launch readiness
    before this demo action is available. No request body — the actual
    provider call pulls purchase_price/purchase_type off the stored
    DomainResult (populated back when the domain search ran).
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
                message="Simulate Registration is only available once the project is READY.",
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

        simulate_registration_task.delay(str(task_id), str(domain_result.id))

        return Response(
            {
                "domain_id": str(domain_result.id),
                "status": "PROCESSING",
                "task_id": str(task_id),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class DomainPrivacyToggleView(APIView):
    """
    Toggles WHOIS privacy for a domain in the name.com sandbox, as a
    background task. Ownership enforced via domain_result.project.user,
    same pattern as DomainRegistrationSimulateView — this endpoint also
    hangs off /domains/{id}/, not /projects/{id}/....

    Gated the same way as Simulate Registration
    (LaunchProject.status == READY): toggling privacy on a domain that
    was never registered in the sandbox would just 404 from name.com
    itself, so this reuses the existing readiness gate rather than
    inventing a new precondition.
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
                message="Toggling WHOIS privacy is only available once the project is READY.",
                status_code=status.HTTP_409_CONFLICT,
            )
        serializer = TogglePrivacySerializer(data=request.data)
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
        toggle_domain_privacy_task.delay(
            str(task_id), str(domain_result.id), serializer.validated_data["enabled"]
        )
        return Response(
            {
                "domain_id": str(domain_result.id),
                "status": "PROCESSING",
                "task_id": str(task_id),
            },
            status=status.HTTP_202_ACCEPTED,
        )