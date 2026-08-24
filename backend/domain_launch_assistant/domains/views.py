# domain_launch_assistant/domains/views.py

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from domain_launch_assistant.brands.models import BrandIdea
from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComTimeoutError,
)
from domain_launch_assistant.domains.models import DomainResult, DomainSearch
from domain_launch_assistant.domains.serializers import (
    DomainResultSerializer,
    DomainSearchRequestSerializer,
    DomainSearchSerializer,
    SelectDomainSerializer,
)

from domain_launch_assistant.domains.services.domain_search import (
    DomainSearchError,
    DomainSearchInputError,
    DomainSearchProviderError,
    DomainSearchService,
    DomainSearchTimeoutError,
)

from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.utils.exceptions import api_error

import uuid

from django.conf import settings


class DomainSearchStartView(APIView):
    """
    Start a domain availability search for a launch project, scoped to
    one of its brand ideas.

    Corresponds to api-contract.md section 15.
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

        try:
            search = DomainSearchService().start_search(
                project=project,
                brand_idea=brand_idea,
                extensions=serializer.validated_data["extensions"],
            )

        except DomainSearchInputError as exc:
            return api_error(
                code="VALIDATION_ERROR",
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        except DomainSearchTimeoutError:
            return api_error(
                code="EXTERNAL_API_TIMEOUT",
                message="The domain provider did not respond. Please try again.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        except DomainSearchProviderError:
            return api_error(
                code="EXTERNAL_API_ERROR",
                message="Domain availability is temporarily unavailable.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except DomainSearchError as exc:
            return api_error(
                code="DOMAIN_CHECK_FAILED",
                message=str(exc),
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        except IntegrityError:
            return api_error(
                code="DOMAIN_CHECK_FAILED",
                message="Domain search produced conflicting results. Please try again.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "search_id": str(search.id),
                "project_id": str(project.id),
                "status": search.status,
                # Placeholder until Celery is introduced.
                "task_id": str(uuid.uuid4()),
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
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        results = DomainResult.objects.filter(project=project)

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