# Standard Library
import uuid

# Django
from django.db import IntegrityError
from django.shortcuts import get_object_or_404

# Django REST Framework
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# Local Project App Imports
from domain_launch_assistant.core.integrations.gemini.client import GeminiClientError
from domain_launch_assistant.brands.models import BrandIdea
from domain_launch_assistant.brands.serializers import BrandIdeaSerializer
from domain_launch_assistant.brands.services.brand_generation import (
    BrandGenerationError,
    BrandGenerationService,
)
from domain_launch_assistant.brands.tasks import generate_brand_ideas_task
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.tasks.models import TaskRecord
from domain_launch_assistant.utils.exceptions import api_error



class BrandGenerateView(APIView):
    """
    Kicks off brand-idea generation as a background task. Validation
    that doesn't need Gemini (count type/range, project ownership)
    still happens synchronously here — only the Gemini call and the
    persistence step move into generate_brand_ideas_task.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        count = request.data.get("count", 5)

        try:
            count = int(count)
        except (TypeError, ValueError):
            return api_error(
                code="VALIDATION_ERROR",
                message="count must be an integer.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if count < 1:
            return api_error(
                code="VALIDATION_ERROR",
                message="count must be greater than 0.",
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

        generate_brand_ideas_task.delay(str(task_id), str(project.id), count)

        return Response(
            {"task_id": str(task_id), "status": "PROCESSING"},
            status=status.HTTP_202_ACCEPTED,
        )
class BrandIdeaListView(APIView):
    """
    List all brand ideas belonging to a launch project.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        brand_ideas = BrandIdea.objects.filter(
            project=project,
        ).order_by("-created_at")

        serializer = BrandIdeaSerializer(
            brand_ideas,
            many=True,
        )

        return Response({"results": serializer.data})


class BrandIdeaSelectView(APIView):
    """
    Select a brand idea for a launch project.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(
            LaunchProject,
            id=project_id,
            user=request.user,
        )

        brand_id = request.data.get("brand_id")
        if not brand_id:
            return api_error(
                code="VALIDATION_ERROR",
                message="brand_id is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        brand_idea = get_object_or_404(
            BrandIdea,
            id=brand_id,
            project=project,
        )

        BrandIdea.objects.filter(
            project=project,
        ).update(
            is_selected=False,
        )

        brand_idea.is_selected = True
        brand_idea.save(update_fields=["is_selected"])

        project.selected_brand = brand_idea
        project.status = LaunchProject.Status.BRANDS_READY
        project.save(update_fields=["selected_brand", "status"])

        return Response(
            {
                "project_id": str(project.id),
                "selected_brand": BrandIdeaSerializer(brand_idea).data,
                "status": project.status,
            }
        )