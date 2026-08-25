import uuid

import pytest

from domain_launch_assistant.tasks.models import TaskRecord


@pytest.mark.django_db
def test_task_detail_success(auth_client_a, project_a):
    task = TaskRecord.objects.create(
        task_id=uuid.uuid4(),
        project=project_a,
        status=TaskRecord.Status.SUCCESS,
        result={"foo": "bar"},
    )

    response = auth_client_a.get(f"/api/v1/tasks/{task.task_id}/")

    assert response.status_code == 200
    assert response.data["task_id"] == str(task.task_id)
    assert response.data["status"] == "SUCCESS"
    assert response.data["result"] == {"foo": "bar"}
    assert response.data["error"] is None


@pytest.mark.django_db
def test_task_detail_with_error(auth_client_a, project_a):
    task = TaskRecord.objects.create(
        task_id=uuid.uuid4(),
        project=project_a,
        status=TaskRecord.Status.FAILURE,
        error_code="AI_GENERATION_FAILED",
        error_message="Brand generation could not be completed. Please try again.",
    )

    response = auth_client_a.get(f"/api/v1/tasks/{task.task_id}/")

    assert response.status_code == 200
    assert response.data["error"] == {
        "code": "AI_GENERATION_FAILED",
        "message": "Brand generation could not be completed. Please try again.",
    }


@pytest.mark.django_db
def test_task_detail_cross_user_404(auth_client_b, project_a):
    task = TaskRecord.objects.create(
        task_id=uuid.uuid4(),
        project=project_a,
        status=TaskRecord.Status.PENDING,
    )

    response = auth_client_b.get(f"/api/v1/tasks/{task.task_id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_task_detail_unauthenticated(client, project_a):
    task = TaskRecord.objects.create(
        task_id=uuid.uuid4(),
        project=project_a,
        status=TaskRecord.Status.PENDING,
    )

    response = client.get(f"/api/v1/tasks/{task.task_id}/")

    assert response.status_code == 401