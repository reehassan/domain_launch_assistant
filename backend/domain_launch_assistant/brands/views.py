from django.db import IntegrityError
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from domain_launch_assistant.brands.models import BrandIdea
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.brands.serializers import BrandIdeaSerializer
from domain_launch_assistant.brands.clients.gemini import GeminiClientError
from domain_launch_assistant.utils.exceptions import api_error
from domain_launch_assistant.brands.services.brand_generation import (
    BrandGenerationError,
    BrandGenerationService,
)


class BrandGenerateView(APIView):
    """
    Generate brand ideas for a launch project.
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

        try:
            brand_ideas = BrandGenerationService().generate_brand_ideas(
                project=project,
                count=count,
            )
        except BrandGenerationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except GeminiClientError:
            return Response(
                {
                    "error": {
                        "code": "AI_GENERATION_FAILED",
                        "message": "Brand generation could not be completed. Please try again.",
                    }
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except IntegrityError:
            return Response(
                {
                    "error": {
                        "code": "AI_GENERATION_FAILED",
                        "message": "Brand generation produced conflicting results. Please try again.",
                    }
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = BrandIdeaSerializer(
            brand_ideas,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
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

        return Response(serializer.data)


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