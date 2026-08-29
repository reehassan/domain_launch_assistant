import pytest
from rest_framework import status
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestRegistration:
    def test_register_creates_user(self, api_client, django_user_model):
        response = api_client.post(
            "/api/v1/auth/register/",
            {
                "username": "founder1",
                "email": "founder1@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert django_user_model.objects.filter(username="founder1").exists()
        # password must never be echoed back
        assert "password" not in response.data

    def test_register_duplicate_username_fails(self, api_client, django_user_model):
        django_user_model.objects.create_user(
            username="founder1",
            email="existing@example.com",
            password="StrongPass123!",
        )
        response = api_client.post(
            "/api/v1/auth/register/",
            {
                "username": "founder1",
                "email": "new@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"
        assert "username" in response.data["error"]["details"]

    def test_register_duplicate_email_fails(self, api_client, django_user_model):
        """
        Ticket 5 spike: confirms duplicate email goes through the same
        DRF UniqueValidator -> VALIDATION_ERROR/400 path as duplicate
        username, rather than the 409 CONFLICT api-contract.md §4.1
        previously (incorrectly) documented as a possible outcome.
        RegisterView does no IntegrityError handling — this is purely
        DRF's ModelSerializer default field-level validation.
        """
        django_user_model.objects.create_user(
            username="existingfounder",
            email="founder1@example.com",
            password="StrongPass123!",
        )
        response = api_client.post(
            "/api/v1/auth/register/",
            {
                "username": "newfounder",
                "email": "founder1@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"
        assert "email" in response.data["error"]["details"]

    def test_register_missing_password_fails(self, api_client):
        response = api_client.post(
            "/api/v1/auth/register/",
            {"username": "founder1", "email": "founder1@example.com"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestLogin:
    @pytest.fixture(autouse=True)
    def _existing_user(self, django_user_model):
        self.user = django_user_model.objects.create_user(
            username="founder1",
            email="founder1@example.com",
            password="StrongPass123!",
        )

    def test_login_success(self, api_client):
        response = api_client.post(
            "/api/v1/auth/login/",
            {"username": "founder1", "password": "StrongPass123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_invalid_credentials(self, api_client):
        response = api_client.post(
            "/api/v1/auth/login/",
            {"username": "founder1", "password": "WrongPassword!"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "access" not in response.data

    def test_login_nonexistent_user(self, api_client):
        response = api_client.post(
            "/api/v1/auth/login/",
            {"username": "doesnotexist", "password": "whatever123"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMe:
    @pytest.fixture(autouse=True)
    def _existing_user(self, django_user_model):
        self.user = django_user_model.objects.create_user(
            username="founder1",
            email="founder1@example.com",
            password="StrongPass123!",
        )

    def test_me_authenticated(self, api_client):
        login = api_client.post(
            "/api/v1/auth/login/",
            {"username": "founder1", "password": "StrongPass123!"},
            format="json",
        )
        token = login.data["access"]
        response = api_client.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == "founder1"
        assert response.data["email"] == "founder1@example.com"

    def test_me_unauthenticated(self, api_client):
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_invalid_token(self, api_client):
        response = api_client.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION="Bearer not-a-real-token",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED