import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.fixture
def user_a(django_user_model):
    return django_user_model.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="pass12345",
    )


@pytest.fixture
def user_b(django_user_model):
    return django_user_model.objects.create_user(
        username="bob",
        email="bob@example.com",
        password="pass12345",
    )


def _client_for(user):
    client = APIClient()
    token = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def auth_client_a(user_a):
    return _client_for(user_a)


@pytest.fixture
def auth_client_b(user_b):
    return _client_for(user_b)