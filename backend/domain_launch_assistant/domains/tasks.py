# domain_launch_assistant/domains/tasks.py
import json

from celery import shared_task
from django.db import IntegrityError
from rest_framework.renderers import JSONRenderer

from domain_launch_assistant.domains.models import DomainSearch
from domain_launch_assistant.domains.serializers import DomainResultSerializer
from domain_launch_assistant.domains.services.domain_search import (
    DomainSearchError,
    DomainSearchInputError,
    DomainSearchProviderError,
    DomainSearchService,
    DomainSearchTimeoutError,
)
from domain_launch_assistant.tasks.models import TaskRecord


@shared_task
def check_domains_task(task_id: str, search_id: str) -> None:
    """
    Background counterpart of the old synchronous DomainSearchStartView
    body. search_id points at a DomainSearch row the view already
    created as PENDING — this task runs the provider call and persists
    results, writing outcome to TaskRecord instead of an HTTP response.

    Exception order matters: the three specific subclasses must be
    caught before the generic DomainSearchError, same as the original
    view's except-chain.
    """
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])

    search = DomainSearch.objects.get(id=search_id)

    try:
        DomainSearchService().run_search(search)
    except DomainSearchInputError as exc:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "VALIDATION_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainSearchTimeoutError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_TIMEOUT"
        task.error_message = "The domain provider did not respond. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainSearchProviderError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = "Domain availability is temporarily unavailable."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainSearchError as exc:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "DOMAIN_CHECK_FAILED"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except IntegrityError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "DOMAIN_CHECK_FAILED"
        task.error_message = "Domain search produced conflicting results. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return

    task.status = TaskRecord.Status.SUCCESS
    # DomainResultSerializer has no PrimaryKeyRelatedField (unlike
    # BrandIdeaSerializer's "project" field in brands/tasks.py), so this
    # round-trip isn't fixing a known bug here — it's the same defensive
    # pattern applied for consistency, in case a field is ever added
    # later that isn't already JSON-primitive.
    results = search.results.all().order_by("-checked_at")
    rendered = JSONRenderer().render(DomainResultSerializer(results, many=True).data)
    task.result = {
        "search_id": str(search.id),
        "status": search.status,
        "results": json.loads(rendered),
    }
    task.save(update_fields=["status", "result"])