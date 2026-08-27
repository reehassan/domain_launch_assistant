from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from domain_launch_assistant.core.integrations.gemini.client import GeminiClientError
from domain_launch_assistant.brands.models import BrandIdea
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.tasks.models import TaskRecord

pytestmark = pytest.mark.django_db


def _mock_gemini():
    return patch(
        "domain_launch_assistant.brands.services.brand_generation.GeminiClient"
    )

class TestGenerateBrands:
    def test_generate_brands_success(self, auth_client_a, project_a):
        with _mock_gemini() as MockClient:
            instance = MockClient.return_value
            instance.generate_brand_ideas.return_value = {
                "brands": [
                    {"name": "LedgerMind", "description": "desc one"},
                    {"name": "Balancely", "description": "desc two"},
                ]
            }
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/generate-brands/",
                {"count": 2},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["status"] == "PROCESSING"

        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS
        names = {b["name"] for b in task.result}
        assert names == {"LedgerMind", "Balancely"}
        assert BrandIdea.objects.filter(project=project_a).count() == 2

    def test_generate_brands_default_count(self, auth_client_a, project_a):
        with _mock_gemini() as MockClient:
            instance = MockClient.return_value
            instance.generate_brand_ideas.return_value = {
                "brands": [
                    {"name": f"Brand{i}", "description": "desc"} for i in range(5)
                ]
            }
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/generate-brands/",
                {},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        instance.generate_brand_ideas.assert_called_once()
        _, kwargs = instance.generate_brand_ideas.call_args
        assert kwargs["count"] == 5

        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS

    def test_generate_brands_invalid_count_type(self, auth_client_a, project_a):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/generate-brands/",
            {"count": "abc"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_generate_brands_count_zero(self, auth_client_a, project_a):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/generate-brands/",
            {"count": 0},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_generate_brands_unauthenticated(self, project_a):
        client = APIClient()
        response = client.post(
            f"/api/v1/projects/{project_a.id}/generate-brands/",
            {"count": 2},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_generate_brands_other_users_project(self, auth_client_a, project_b):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_b.id}/generate-brands/",
            {"count": 2},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["error"]["code"] == "NOT_FOUND"

    def test_generate_brands_gemini_failure_marks_task_failed(
        self, auth_client_a, project_a
    ):
        with _mock_gemini() as MockClient:
            instance = MockClient.return_value
            instance.generate_brand_ideas.side_effect = GeminiClientError("boom")
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/generate-brands/",
                {"count": 2},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "AI_GENERATION_FAILED"

    def test_generate_brands_wrong_count_returned_by_gemini_marks_task_failed(
        self, auth_client_a, project_a
    ):
        with _mock_gemini() as MockClient:
            instance = MockClient.return_value
            instance.generate_brand_ideas.return_value = {
                "brands": [{"name": "OnlyOne", "description": "desc"}]
            }
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/generate-brands/",
                {"count": 3},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "BRAND_GENERATION_INVALID"
        assert BrandIdea.objects.filter(project=project_a).count() == 0

    def test_generate_brands_duplicate_name_in_existing_project_marks_task_failed(
        self, auth_client_a, project_a
    ):
        """
        Regression test for the original bug #11: a name collision with a
        brand already persisted for this project (case-insensitive) must
        surface as a clean AI_GENERATION_FAILED task failure, not an
        uncaught IntegrityError inside the worker.
        """
        BrandIdea.objects.create(
            project=project_a,
            name="Balancely",
            description="already exists",
        )
        with _mock_gemini() as MockClient:
            instance = MockClient.return_value
            instance.generate_brand_ideas.return_value = {
                "brands": [{"name": "balancely", "description": "same name, different case"}]
            }
            response = auth_client_a.post(
                f"/api/v1/projects/{project_a.id}/generate-brands/",
                {"count": 1},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "AI_GENERATION_FAILED"
        assert BrandIdea.objects.filter(project=project_a).count() == 1
class TestListBrands:
    def test_list_brands_returns_only_this_projects_brands(self, auth_client_a, project_a, project_b):
        BrandIdea.objects.create(project=project_a, name="Mine", description="d")
        BrandIdea.objects.create(project=project_b, name="NotMine", description="d")

        response = auth_client_a.get(f"/api/v1/projects/{project_a.id}/brands/")

        assert response.status_code == status.HTTP_200_OK
        names = [b["name"] for b in response.data]
        assert names == ["Mine"]

    def test_list_brands_response_shape_has_no_updated_at(self, auth_client_a, project_a):
        """
        Regression test: BrandIdea has no updated_at field. The serializer
        previously listed it anyway, which crashed .data access with a
        raw 500 the moment this endpoint was hit.
        """
        BrandIdea.objects.create(project=project_a, name="Mine", description="d")

        response = auth_client_a.get(f"/api/v1/projects/{project_a.id}/brands/")

        assert response.status_code == status.HTTP_200_OK
        assert "updated_at" not in response.data[0]
        assert set(response.data[0].keys()) == {
            "id", "project", "name", "description", "is_selected", "created_at",
        }

    def test_list_brands_other_users_project(self, auth_client_a, project_b):
        response = auth_client_a.get(f"/api/v1/projects/{project_b.id}/brands/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_brands_unauthenticated(self, project_a):
        client = APIClient()
        response = client.get(f"/api/v1/projects/{project_a.id}/brands/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestSelectBrand:
    def test_select_brand_success(self, auth_client_a, project_a):
        brand = BrandIdea.objects.create(project=project_a, name="Pick Me", description="d")

        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/select-brand/",
            {"brand_id": str(brand.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == LaunchProject.Status.BRANDS_READY
        assert response.data["selected_brand"]["id"] == str(brand.id)

        brand.refresh_from_db()
        project_a.refresh_from_db()
        assert brand.is_selected is True
        assert project_a.status == LaunchProject.Status.BRANDS_READY
        assert project_a.selected_brand_id == brand.id

    def test_select_brand_switches_previous_selection_off(self, auth_client_a, project_a):
        first = BrandIdea.objects.create(
            project=project_a, name="First", description="d", is_selected=True
        )
        second = BrandIdea.objects.create(project=project_a, name="Second", description="d")

        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/select-brand/",
            {"brand_id": str(second.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.is_selected is False
        assert second.is_selected is True

    def test_select_brand_missing_brand_id(self, auth_client_a, project_a):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/select-brand/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_select_brand_nonexistent_brand_id(self, auth_client_a, project_a):
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/select-brand/",
            {"brand_id": "00000000-0000-0000-0000-000000000000"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["error"]["code"] == "NOT_FOUND"

    def test_select_brand_belonging_to_other_project_fails(
        self, auth_client_a, project_a, project_b
    ):
        foreign_brand = BrandIdea.objects.create(
            project=project_b, name="Not Yours", description="d"
        )
        response = auth_client_a.post(
            f"/api/v1/projects/{project_a.id}/select-brand/",
            {"brand_id": str(foreign_brand.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_select_brand_other_users_project(self, auth_client_a, project_b):
        brand = BrandIdea.objects.create(project=project_b, name="X", description="d")
        response = auth_client_a.post(
            f"/api/v1/projects/{project_b.id}/select-brand/",
            {"brand_id": str(brand.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_select_brand_unauthenticated(self, project_a):
        brand = BrandIdea.objects.create(project=project_a, name="X", description="d")
        client = APIClient()
        response = client.post(
            f"/api/v1/projects/{project_a.id}/select-brand/",
            {"brand_id": str(brand.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED