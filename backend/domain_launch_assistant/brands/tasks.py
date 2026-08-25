from django.db import IntegrityError

from celery import shared_task
from rest_framework.renderers import JSONRenderer

from domain_launch_assistant.brands.clients.gemini import GeminiClientError
from domain_launch_assistant.brands.serializers import BrandIdeaSerializer
from domain_launch_assistant.brands.services.brand_generation import (
    BrandGenerationError,
    BrandGenerationService,
)
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.tasks.models import TaskRecord


@shared_task
def generate_brand_ideas_task(task_id: str, project_id: str, count: int) -> None:
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])

    project = LaunchProject.objects.get(id=project_id)

    try:
        brand_ideas = BrandGenerationService().generate_brand_ideas(
            project=project,
            count=count,
        )
    except BrandGenerationError as exc:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "BRAND_GENERATION_INVALID"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except GeminiClientError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "AI_GENERATION_FAILED"
        task.error_message = "Brand generation could not be completed. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except IntegrityError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "AI_GENERATION_FAILED"
        task.error_message = "Brand generation produced conflicting results. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return

    task.status = TaskRecord.Status.SUCCESS
    # .data from a ModelSerializer isn't guaranteed JSON-primitive —
    # PrimaryKeyRelatedField (the "project" field here) returns the raw
    # UUID .pk, not a string, unlike UUIDField. Rendering through DRF's
    # own JSONRenderer and reloading forces the exact same UUID/datetime
    # stringification the HTTP response path gets for free, so this
    # matches what the old synchronous 201 response actually returned.
    import json
    rendered = JSONRenderer().render(BrandIdeaSerializer(brand_ideas, many=True).data)
    task.result = json.loads(rendered)
    task.save(update_fields=["status", "result"])