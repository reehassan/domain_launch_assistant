# domain_launch_assistant/dns/tests/test_dns_records.py

from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from domain_launch_assistant.dns.services.dns_records import DnsRecordsGuardError, DnsRecordsService
from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComTimeoutError,
)
from domain_launch_assistant.domains.clients.namecom import NameComClient
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.tasks.models import TaskRecord

pytestmark = pytest.mark.django_db


def _mock_dns_records_namecom():
    """
    Patches NameComClient at the point dns_records.py imports it, so
    DnsRecordsService() picks up the mock without any code changes —
    same pattern as _mock_registration_namecom() in test_domains.py.
    """
    return patch("domain_launch_assistant.dns.services.dns_records.NameComClient")


def _make_ready(project, domain_result):
    project.selected_domain = domain_result
    project.status = LaunchProject.Status.READY
    project.save(update_fields=["selected_domain", "status"])


class TestListDnsRecords:
    def test_list_success(self, auth_client_a, project_a, domain_result_a):
        _make_ready(project_a, domain_result_a)

        with _mock_dns_records_namecom() as MockClient:
            instance = MockClient.return_value
            instance.list_records.return_value = [
                {
                    "id": 1,
                    "domainName": domain_result_a.domain,
                    "host": "www",
                    "fqdn": f"www.{domain_result_a.domain}.",
                    "type": "A",
                    "answer": "10.0.0.1",
                    "ttl": 300,
                    "priority": None,
                }
            ]
            response = auth_client_a.get(
                f"/api/v1/domains/{domain_result_a.id}/dns-records/"
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0]["answer"] == "10.0.0.1"

    def test_list_not_ready_returns_409(self, auth_client_a, project_a, domain_result_a):
        # project_a.status defaults to DRAFT — never advanced to READY.
        response = auth_client_a.get(
            f"/api/v1/domains/{domain_result_a.id}/dns-records/"
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "CONFLICT"

    def test_list_provider_timeout_returns_504(
        self, auth_client_a, project_a, domain_result_a
    ):
        _make_ready(project_a, domain_result_a)

        with _mock_dns_records_namecom() as MockClient:
            instance = MockClient.return_value
            instance.list_records.side_effect = NameComTimeoutError("timed out")
            response = auth_client_a.get(
                f"/api/v1/domains/{domain_result_a.id}/dns-records/"
            )

        assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
        assert response.data["error"]["code"] == "EXTERNAL_API_TIMEOUT"

    def test_list_provider_error_returns_502(
        self, auth_client_a, project_a, domain_result_a
    ):
        _make_ready(project_a, domain_result_a)

        with _mock_dns_records_namecom() as MockClient:
            instance = MockClient.return_value
            instance.list_records.side_effect = NameComAPIError("server error")
            response = auth_client_a.get(
                f"/api/v1/domains/{domain_result_a.id}/dns-records/"
            )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert response.data["error"]["code"] == "EXTERNAL_API_ERROR"

    def test_list_other_users_domain_fails(self, auth_client_a, domain_result_b):
        response = auth_client_a.get(
            f"/api/v1/domains/{domain_result_b.id}/dns-records/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_unauthenticated(self, domain_result_a):
        client = APIClient()
        response = client.get(f"/api/v1/domains/{domain_result_a.id}/dns-records/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCreateDnsRecord:
    def test_create_success(self, auth_client_a, project_a, domain_result_a):
        _make_ready(project_a, domain_result_a)

        with _mock_dns_records_namecom() as MockClient:
            instance = MockClient.return_value
            instance.create_record.return_value = {
                "id": 42,
                "domainName": domain_result_a.domain,
                "host": "www",
                "fqdn": f"www.{domain_result_a.domain}.",
                "type": "A",
                "answer": "10.0.0.1",
                "ttl": 300,
                "priority": None,
            }
            response = auth_client_a.post(
                f"/api/v1/domains/{domain_result_a.id}/create-dns-record/",
                {"host": "www", "type": "A", "answer": "10.0.0.1"},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS
        assert task.result["answer"] == "10.0.0.1"

    def test_create_not_ready_returns_409(self, auth_client_a, project_a, domain_result_a):
        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_a.id}/create-dns-record/",
            {"host": "www", "type": "A", "answer": "10.0.0.1"},
            format="json",
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "CONFLICT"

    def test_create_missing_priority_for_mx_returns_400(
        self, auth_client_a, project_a, domain_result_a
    ):
        _make_ready(project_a, domain_result_a)
        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_a.id}/create-dns-record/",
            {"host": "", "type": "MX", "answer": "mail.example.com"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_create_invalid_type_returns_400(
        self, auth_client_a, project_a, domain_result_a
    ):
        _make_ready(project_a, domain_result_a)
        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_a.id}/create-dns-record/",
            {"host": "www", "type": "NOT_A_TYPE", "answer": "10.0.0.1"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_provider_timeout_marks_task_failed(
        self, auth_client_a, project_a, domain_result_a
    ):
        _make_ready(project_a, domain_result_a)

        with _mock_dns_records_namecom() as MockClient:
            instance = MockClient.return_value
            instance.create_record.side_effect = NameComTimeoutError("timed out")
            response = auth_client_a.post(
                f"/api/v1/domains/{domain_result_a.id}/create-dns-record/",
                {"host": "www", "type": "A", "answer": "10.0.0.1"},
                format="json",
            )

        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "EXTERNAL_API_TIMEOUT"

    def test_create_production_base_url_fails_loudly(
        self, auth_client_a, project_a, domain_result_a, settings
    ):
        """
        Same safety mechanism as registration_simulation.py's guard: if
        NAMECOM_TEST_BASE_URL is ever misconfigured to a production-shaped
        host, the task must fail loudly with INTERNAL_ERROR — not
        silently touch real DNS.
        """
        _make_ready(project_a, domain_result_a)
        settings.NAMECOM_TEST_BASE_URL = "https://api.name.com/core/v1"

        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_a.id}/create-dns-record/",
            {"host": "www", "type": "A", "answer": "10.0.0.1"},
            format="json",
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.FAILURE
        assert task.error_code == "INTERNAL_ERROR"

    def test_guard_refuses_production_base_url_directly(self, settings):
        """Service-level unit test of the guard, independent of task/view wiring."""
        settings.NAMECOM_TEST_BASE_URL = "https://api.name.com/core/v1"
        with pytest.raises(DnsRecordsGuardError):
            DnsRecordsService()

    def test_guard_refuses_injected_production_client(self):
        production_client = NameComClient(
            username="u", token="t", base_url="https://api.name.com/core/v1"
        )
        with pytest.raises(DnsRecordsGuardError):
            DnsRecordsService(namecom_client=production_client)

    def test_create_other_users_domain_fails(self, auth_client_a, domain_result_b):
        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_b.id}/create-dns-record/",
            {"host": "www", "type": "A", "answer": "10.0.0.1"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_unauthenticated(self, domain_result_a):
        client = APIClient()
        response = client.post(
            f"/api/v1/domains/{domain_result_a.id}/create-dns-record/",
            {"host": "www", "type": "A", "answer": "10.0.0.1"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED