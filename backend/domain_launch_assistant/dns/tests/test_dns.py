# domain_launch_assistant/dns/tests/test_dns.py

import socket
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from domain_launch_assistant.dns.models import DomainCheck
from domain_launch_assistant.domains.models import DomainResult
from domain_launch_assistant.launches.models import LaunchProject
from domain_launch_assistant.tasks.models import TaskRecord

pytestmark = pytest.mark.django_db


def _mock_dns_lookup():
    """
    Patches socket.gethostbyname at the point check_domain.py imports
    it, so CheckDomainService picks up the mock without any code
    changes — same pattern as _mock_namecom() in test_domains.py.
    """
    return patch(
        "domain_launch_assistant.dns.services.check_domain.socket.gethostbyname"
    )


class TestCheckDomain:
    def test_check_success_both_types(self, auth_client_a, project_a, domain_result_a):
        # Select the domain first — DOMAIN_READINESS PASS requires the
        # result to actually be the project's selected domain.
        project_a.selected_domain = domain_result_a
        project_a.status = LaunchProject.Status.DOMAIN_SELECTED
        project_a.save(update_fields=["selected_domain", "status"])

        with _mock_dns_lookup() as mock_lookup:
            mock_lookup.return_value = "203.0.113.10"
            response = auth_client_a.post(
                f"/api/v1/domains/{domain_result_a.id}/check/",
                {"check_types": ["DNS_RESOLUTION", "DOMAIN_READINESS"]},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["domain_id"] == str(domain_result_a.id)
        assert "task_id" in response.data
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS

        checks = DomainCheck.objects.filter(domain_result=domain_result_a)
        assert checks.count() == 2

        resolution = checks.get(check_type=DomainCheck.CheckType.DNS_RESOLUTION)
        assert resolution.status == DomainCheck.Status.PASS
        assert resolution.actual_value == "203.0.113.10"
        assert resolution.checked_at is not None

        readiness = checks.get(check_type=DomainCheck.CheckType.DOMAIN_READINESS)
        assert readiness.status == DomainCheck.Status.PASS

        # Both requested checks PASSed, so the project must advance all
        # the way to READY, not stop at VERIFYING_DNS — see
        # TestDnsReadyTransition below for the partial-failure cases.
        project_a.refresh_from_db()
        assert project_a.status == LaunchProject.Status.READY

    def test_dns_resolution_no_record_is_fail_not_error(
        self, auth_client_a, project_a, domain_result_a
    ):
        """
        A domain that simply doesn't resolve yet is FAIL — the check
        ran successfully, the configuration just isn't there.
        data-model.md section 6 draws this distinction explicitly.
        """
        with _mock_dns_lookup() as mock_lookup:
            mock_lookup.side_effect = socket.gaierror("not found")
            response = auth_client_a.post(
                f"/api/v1/domains/{domain_result_a.id}/check/",
                {"check_types": ["DNS_RESOLUTION"]},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        check = DomainCheck.objects.get(domain_result=domain_result_a)
        assert check.status == DomainCheck.Status.FAIL
        assert check.actual_value is None

    def test_dns_resolution_lookup_failure_is_error_not_fail(
        self, auth_client_a, project_a, domain_result_a
    ):
        """
        A lookup that couldn't complete at all (network/resolver
        issue) is ERROR — distinct from FAIL, which means the check
        ran and found nothing.
        """
        with _mock_dns_lookup() as mock_lookup:
            mock_lookup.side_effect = OSError("network unreachable")
            response = auth_client_a.post(
                f"/api/v1/domains/{domain_result_a.id}/check/",
                {"check_types": ["DNS_RESOLUTION"]},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        check = DomainCheck.objects.get(domain_result=domain_result_a)
        assert check.status == DomainCheck.Status.ERROR
        # Regression: an ERROR-status check is a captured outcome, not
        # a task crash — the task itself must still report SUCCESS.
        task = TaskRecord.objects.get(task_id=response.data["task_id"])
        assert task.status == TaskRecord.Status.SUCCESS

    def test_domain_readiness_fail_when_not_selected(
        self, auth_client_a, project_a, domain_result_a
    ):
        # project_a.selected_domain deliberately left unset.
        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_a.id}/check/",
            {"check_types": ["DOMAIN_READINESS"]},
            format="json",
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        check = DomainCheck.objects.get(domain_result=domain_result_a)
        assert check.status == DomainCheck.Status.FAIL
        assert "not the project's selected domain" in check.message

    def test_domain_readiness_fail_when_no_longer_available(
        self, auth_client_a, project_a, domain_result_a
    ):
        project_a.selected_domain = domain_result_a
        project_a.save(update_fields=["selected_domain"])

        # Simulate a result that's stale/no longer available, bypassing
        # select-domain's own freshness/availability gate since we're
        # testing DOMAIN_READINESS's read of current state directly.
        domain_result_a.status = DomainResult.Status.TAKEN
        domain_result_a.available = False
        domain_result_a.save(update_fields=["status", "available"])

        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_a.id}/check/",
            {"check_types": ["DOMAIN_READINESS"]},
            format="json",
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        check = DomainCheck.objects.get(domain_result=domain_result_a)
        assert check.status == DomainCheck.Status.FAIL
        assert "no longer marked available" in check.message

    def test_unsupported_check_type_returns_400_and_persists_nothing(
        self, auth_client_a, project_a, domain_result_a
    ):
        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_a.id}/check/",
            {"check_types": ["DNS_CONFIGURATION"]},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"
        assert DomainCheck.objects.filter(domain_result=domain_result_a).count() == 0

    def test_mixed_supported_and_unsupported_persists_nothing(
        self, auth_client_a, project_a, domain_result_a
    ):
        """
        Regression test: one unsupported check_type in the list must
        reject the whole request atomically, not partially process the
        supported ones.
        """
        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_a.id}/check/",
            {"check_types": ["DNS_RESOLUTION", "DNS_CONFIGURATION"]},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert DomainCheck.objects.filter(domain_result=domain_result_a).count() == 0

    def test_missing_check_types(self, auth_client_a, project_a, domain_result_a):
        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_a.id}/check/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_invalid_check_type_value(self, auth_client_a, project_a, domain_result_a):
        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_a.id}/check/",
            {"check_types": ["NOT_A_REAL_TYPE"]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_check_domain_belonging_to_other_user_fails(
        self, auth_client_a, domain_result_b
    ):
        response = auth_client_a.post(
            f"/api/v1/domains/{domain_result_b.id}/check/",
            {"check_types": ["DNS_RESOLUTION"]},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert DomainCheck.objects.filter(domain_result=domain_result_b).count() == 0

    def test_check_unauthenticated(self, domain_result_a):
        client = APIClient()
        response = client.post(
            f"/api/v1/domains/{domain_result_a.id}/check/",
            {"check_types": ["DNS_RESOLUTION"]},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestListDomainChecks:
    def test_list_returns_checks_for_this_domain_result(
        self, auth_client_a, project_a, domain_result_a
    ):
        DomainCheck.objects.create(
            project=project_a,
            domain_result=domain_result_a,
            check_type=DomainCheck.CheckType.DNS_RESOLUTION,
            status=DomainCheck.Status.PASS,
        )
        DomainCheck.objects.create(
            project=project_a,
            domain_result=domain_result_a,
            check_type=DomainCheck.CheckType.DOMAIN_READINESS,
            status=DomainCheck.Status.FAIL,
        )

        response = auth_client_a.get(f"/api/v1/domains/{domain_result_a.id}/checks/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_list_empty_when_no_checks_run_yet(
        self, auth_client_a, project_a, domain_result_a
    ):
        response = auth_client_a.get(f"/api/v1/domains/{domain_result_a.id}/checks/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []

    def test_list_other_users_domain_fails(self, auth_client_a, domain_result_b):
        response = auth_client_a.get(f"/api/v1/domains/{domain_result_b.id}/checks/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_unauthenticated(self, domain_result_a):
        client = APIClient()
        response = client.get(f"/api/v1/domains/{domain_result_a.id}/checks/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestDnsReadyTransition:
    """
    Covers the READY-transition rule in run_domain_checks_task: the
    project only advances to READY once every requested check type has
    actually PASSed. This is the gate Feature 5 (Simulate Registration)
    depends on — DomainRegistrationSimulateView 409s unless
    project.status == READY.
    """

    def test_all_checks_pass_transitions_to_ready(
        self, auth_client_a, project_a, domain_result_a
    ):
        project_a.selected_domain = domain_result_a
        project_a.status = LaunchProject.Status.DOMAIN_SELECTED
        project_a.save(update_fields=["selected_domain", "status"])

        with _mock_dns_lookup() as mock_lookup:
            mock_lookup.return_value = "203.0.113.10"
            response = auth_client_a.post(
                f"/api/v1/domains/{domain_result_a.id}/check/",
                {"check_types": ["DNS_RESOLUTION", "DOMAIN_READINESS"]},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        project_a.refresh_from_db()
        assert project_a.status == LaunchProject.Status.READY

    def test_one_check_fails_stays_at_verifying_dns(
        self, auth_client_a, project_a, domain_result_a
    ):
        # selected_domain deliberately left unset, so DOMAIN_READINESS
        # will FAIL even though DNS_RESOLUTION PASSes.
        with _mock_dns_lookup() as mock_lookup:
            mock_lookup.return_value = "203.0.113.10"
            response = auth_client_a.post(
                f"/api/v1/domains/{domain_result_a.id}/check/",
                {"check_types": ["DNS_RESOLUTION", "DOMAIN_READINESS"]},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        checks = DomainCheck.objects.filter(domain_result=domain_result_a)
        assert checks.get(check_type=DomainCheck.CheckType.DOMAIN_READINESS).status == (
            DomainCheck.Status.FAIL
        )

        project_a.refresh_from_db()
        assert project_a.status == LaunchProject.Status.VERIFYING_DNS
        assert project_a.status != LaunchProject.Status.READY

    def test_check_error_stays_at_verifying_dns(
        self, auth_client_a, project_a, domain_result_a
    ):
        project_a.selected_domain = domain_result_a
        project_a.status = LaunchProject.Status.DOMAIN_SELECTED
        project_a.save(update_fields=["selected_domain", "status"])

        with _mock_dns_lookup() as mock_lookup:
            mock_lookup.side_effect = OSError("network unreachable")
            response = auth_client_a.post(
                f"/api/v1/domains/{domain_result_a.id}/check/",
                {"check_types": ["DNS_RESOLUTION", "DOMAIN_READINESS"]},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        checks = DomainCheck.objects.filter(domain_result=domain_result_a)
        assert checks.get(check_type=DomainCheck.CheckType.DNS_RESOLUTION).status == (
            DomainCheck.Status.ERROR
        )
        # DOMAIN_READINESS still PASSes here (domain is selected and
        # available) — the point of this test is that ERROR on the
        # *other* check is still enough to block READY. All-PASS means
        # all, not "no FAILs".
        assert checks.get(check_type=DomainCheck.CheckType.DOMAIN_READINESS).status == (
            DomainCheck.Status.PASS
        )

        project_a.refresh_from_db()
        assert project_a.status == LaunchProject.Status.VERIFYING_DNS
        assert project_a.status != LaunchProject.Status.READY