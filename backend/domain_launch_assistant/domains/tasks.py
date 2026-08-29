# domain_launch_assistant/domains/tasks.py
import json

from celery import shared_task
from django.db import IntegrityError
from rest_framework.renderers import JSONRenderer

import logging

logger = logging.getLogger(__name__)

from domain_launch_assistant.core.integrations.gemini.client import GeminiClientError
from domain_launch_assistant.core.services.domain_recommendation import (
    DomainRecommendationError,
    DomainRecommendationService,
)
from domain_launch_assistant.domains.models import DomainResult, DomainSearch
from domain_launch_assistant.domains.serializers import (
    DomainClaimSerializer,
    DomainRecommendationSerializer,
    DomainResultSerializer,
)
from domain_launch_assistant.domains.services.domain_claims import (
    DomainClaimsError,
    DomainClaimsProviderError,
    DomainClaimsService,
    DomainClaimsTimeoutError,
)
from domain_launch_assistant.domains.services.domain_search import (
    DomainSearchError,
    DomainSearchInputError,
    DomainSearchProviderError,
    DomainSearchService,
    DomainSearchTimeoutError,
)
from domain_launch_assistant.domains.services.registration_simulation import (
    DomainRegistrationSimulationError,
    DomainRegistrationSimulationGuardError,
    DomainRegistrationSimulationProviderError,
    DomainRegistrationSimulationService,
    DomainRegistrationSimulationTimeoutError,
)
from domain_launch_assistant.launches.models import LaunchProject
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
    except Exception:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = "Something went wrong. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        logger.exception(
            "Unhandled error in check_domains_task",
            extra={"task_id": task_id, "search_id": search_id},
        )
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


@shared_task
def check_domain_claims_task(task_id: str, domain_result_id: str) -> None:
    """
    Background counterpart of DomainClaimsCheckView. domain_result_id
    points at an already-persisted DomainResult — this task calls
    name.com's TMCH claims endpoint and, only on success, persists a
    DomainClaim row.

    On DomainClaimsTimeoutError/DomainClaimsProviderError, nothing is
    written: the task fails with EXTERNAL_API_TIMEOUT / EXTERNAL_API_ERROR
    and the founder sees "check failed", never a false "no claims".
    """
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])

    domain_result = DomainResult.objects.get(id=domain_result_id)

    try:
        claim = DomainClaimsService().check_claims(domain_result)
    except DomainClaimsTimeoutError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_TIMEOUT"
        task.error_message = "The trademark claims provider did not respond. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainClaimsProviderError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = "Trademark claims check is temporarily unavailable."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainClaimsError as exc:
        # Defensive catch-all for the base class — no current code path
        # raises DomainClaimsError directly, but this keeps the same
        # exception-order safety net domain_search.py uses.
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except IntegrityError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = "Trademark claims check produced conflicting results. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except Exception:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = "Something went wrong. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        logger.exception(
            "Unhandled error in check_domain_claims_task",
            extra={"task_id": task_id, "domain_result_id": domain_result_id},
        )
        return

    task.status = TaskRecord.Status.SUCCESS
    rendered = JSONRenderer().render(DomainClaimSerializer(claim).data)
    task.result = json.loads(rendered)
    task.save(update_fields=["status", "result"])


@shared_task
def recommend_domain_task(task_id: str, project_id: str) -> None:
    """
    Background counterpart of DomainRecommendGenerateView. project_id
    points at a LaunchProject the view already validated has a
    completed domain search and at least one AVAILABLE DomainResult —
    this task calls Gemini via DomainRecommendationService and, only on
    success, persists a DomainRecommendation row.

    On DomainRecommendationError (Gemini's pick fails our business
    rules — references a domain that isn't actually available, or
    empty reasoning) or GeminiClientError (the API call/schema
    validation itself failed), nothing is written: the task fails with
    AI_GENERATION_FAILED and the founder sees "recommendation failed",
    never a fabricated or unvalidated pick.
    """
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])

    project = LaunchProject.objects.get(id=project_id)

    try:
        recommendation = DomainRecommendationService().recommend_domain(project)
    except DomainRecommendationError as exc:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "AI_GENERATION_FAILED"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except GeminiClientError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "AI_GENERATION_FAILED"
        task.error_message = "Domain recommendation could not be completed. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except IntegrityError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "AI_GENERATION_FAILED"
        task.error_message = "Domain recommendation produced conflicting results. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except Exception:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = "Something went wrong. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        logger.exception(
            "Unhandled error in recommend_domain_task",
            extra={"task_id": task_id, "project_id": project_id},
        )
        return

    task.status = TaskRecord.Status.SUCCESS
    rendered = JSONRenderer().render(DomainRecommendationSerializer(recommendation).data)
    task.result = json.loads(rendered)
    task.save(update_fields=["status", "result"])


@shared_task
def simulate_registration_task(task_id: str, domain_result_id: str) -> None:
    """
    Background counterpart of DomainRegistrationSimulateView.
    domain_result_id points at an already-persisted DomainResult.
    DomainRegistrationSimulationService builds its own sandbox-only
    NameComClient internally — never the production client used by the
    tasks above. Nothing is persisted beyond TaskRecord: no new model,
    no LaunchProject.status change (data-model.md section 9).
    """
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])

    domain_result = DomainResult.objects.get(id=domain_result_id)

    try:
        result = DomainRegistrationSimulationService().simulate_registration(domain_result)
    except DomainRegistrationSimulationGuardError as exc:
        # The sandbox/production guard tripped. This is a configuration
        # safety violation, not a routine provider failure, so it must
        # fail loudly with its own code rather than being folded into
        # EXTERNAL_API_ERROR where it could be mistaken for a transient
        # outage and retried.
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainRegistrationSimulationTimeoutError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_TIMEOUT"
        task.error_message = "The domain provider did not respond. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainRegistrationSimulationProviderError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = "Sandbox registration is temporarily unavailable."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainRegistrationSimulationError as exc:
        # Defensive catch-all for the base class, same pattern used by
        # check_domain_claims_task's DomainClaimsError handler.
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except Exception:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = "Something went wrong. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        logger.exception(
            "Unhandled error in simulate_registration_task",
            extra={"task_id": task_id, "domain_result_id": domain_result_id},
        )
        return

    task.status = TaskRecord.Status.SUCCESS
    # Plain dict of JSON-primitive values (bool/str) — no model involved,
    # so no serializer round-trip needed here (unlike the tasks above).
    task.result = result
    task.save(update_fields=["status", "result"])


@shared_task
def toggle_domain_privacy_task(task_id: str, domain_result_id: str, enabled: bool) -> None:
    """
    Background counterpart of DomainPrivacyToggleView. domain_result_id
    points at an already-persisted DomainResult — presumed already
    registered in the sandbox via simulate_registration_task. Toggling
    privacy on a domain never sandbox-registered will fail with a 404
    from name.com itself (per their docs: domains must be created in
    sandbox before use), surfaced here the same way as any other
    provider error. Nothing is persisted beyond TaskRecord: same
    discipline as simulate_registration_task — no new model, no
    LaunchProject.status change.
    """
    task = TaskRecord.objects.get(task_id=task_id)
    task.status = TaskRecord.Status.PROCESSING
    task.save(update_fields=["status"])

    domain_result = DomainResult.objects.get(id=domain_result_id)
    try:
        result = DomainRegistrationSimulationService().toggle_privacy(
            domain_result.domain, enabled
        )
    except DomainRegistrationSimulationGuardError as exc:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainRegistrationSimulationTimeoutError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_TIMEOUT"
        task.error_message = "The domain provider did not respond. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainRegistrationSimulationProviderError:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = "Sandbox privacy toggle is temporarily unavailable."
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except DomainRegistrationSimulationError as exc:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "EXTERNAL_API_ERROR"
        task.error_message = str(exc)
        task.save(update_fields=["status", "error_code", "error_message"])
        return
    except Exception:
        task.status = TaskRecord.Status.FAILURE
        task.error_code = "INTERNAL_ERROR"
        task.error_message = "Something went wrong. Please try again."
        task.save(update_fields=["status", "error_code", "error_message"])
        logger.exception(
            "Unhandled error in toggle_domain_privacy_task",
            extra={"task_id": task_id, "domain_result_id": domain_result_id},
        )
        return

    task.status = TaskRecord.Status.SUCCESS
    task.result = result
    task.save(update_fields=["status", "result"])