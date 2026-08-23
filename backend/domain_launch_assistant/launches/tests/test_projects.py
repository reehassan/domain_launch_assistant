import pytest
from rest_framework import status

from domain_launch_assistant.launches.models import LaunchProject

pytestmark = pytest.mark.django_db


class TestCreateProject:
    def test_create_project_authenticated(self, auth_client_a, user_a):
        response = auth_client_a.post(
            "/api/v1/projects/",
            {
                "name": "My Startup",
                "business_description": "An AI-powered domain launch assistant",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        project = LaunchProject.objects.get(id=response.data["id"])
        assert project.user_id == user_a.id
        assert project.status == LaunchProject.Status.DRAFT

    def test_create_project_unauthenticated(self, api_client=None):
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.post(
            "/api/v1/projects/",
            {"name": "My Startup", "business_description": "Some business"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_project_missing_name_fails(self, auth_client_a):
        response = auth_client_a.post(
            "/api/v1/projects/",
            {"business_description": "Some business"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_project_missing_description_fails(self, auth_client_a):
        response = auth_client_a.post(
            "/api/v1/projects/",
            {"name": "My Startup"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestListProjects:
    def test_list_projects_returns_only_own(self, auth_client_a, auth_client_b, user_a, user_b):
        LaunchProject.objects.create(
            user=user_a, name="A's Project", business_description="desc"
        )
        LaunchProject.objects.create(
            user=user_b, name="B's Project", business_description="desc"
        )

        response = auth_client_a.get("/api/v1/projects/")

        assert response.status_code == status.HTTP_200_OK
        names = [p["name"] for p in response.data["results"]] if "results" in response.data else [p["name"] for p in response.data]
        assert names == ["A's Project"]

    def test_list_projects_unauthenticated(self):
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get("/api/v1/projects/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRetrieveProject:
    def test_retrieve_own_project(self, auth_client_a, user_a):
        project = LaunchProject.objects.create(
            user=user_a, name="A's Project", business_description="desc"
        )

        response = auth_client_a.get(f"/api/v1/projects/{project.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(project.id)

    def test_retrieve_other_users_project_fails(self, auth_client_a, user_b):
        other_project = LaunchProject.objects.create(
            user=user_b, name="B's Project", business_description="desc"
        )

        response = auth_client_a.get(f"/api/v1/projects/{other_project.id}/")

        # 404, not 403 — don't leak that the project exists at all
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_project_unauthenticated(self, user_a):
        from rest_framework.test import APIClient

        project = LaunchProject.objects.create(
            user=user_a, name="A's Project", business_description="desc"
        )

        client = APIClient()
        response = client.get(f"/api/v1/projects/{project.id}/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED