# domain_launch_assistant/domains/tests/test_namecom_client.py

from unittest.mock import Mock, patch

import pytest
import requests

from domain_launch_assistant.domains.clients.exceptions import (
    NameComAPIError,
    NameComTimeoutError,
)
from domain_launch_assistant.domains.clients.namecom import NameComClient


def _client(**overrides):
    kwargs = dict(
        username="u",
        token="t",
        base_url="https://api.dev.name.com/core/v1",
        max_retries=3,
        retry_backoff_base=0.5,
    )
    kwargs.update(overrides)
    return NameComClient(**kwargs)


def _response(status_code, payload=None):
    resp = Mock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = "error body"
    resp.json.return_value = payload if payload is not None else {}
    return resp


class TestRequestWithRetry:
    def test_succeeds_first_try_no_retry(self):
        client = _client()
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request, patch(
            "domain_launch_assistant.domains.clients.namecom.time.sleep"
        ) as mock_sleep:
            mock_request.return_value = _response(
                200, {"results": [{"domainName": "ledgerflow.com", "purchasable": True}]}
            )
            results = client.check_availability(["ledgerflow.com"])

        assert results == [{"domainName": "ledgerflow.com", "purchasable": True}]
        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()

    def test_retries_on_timeout_then_succeeds(self):
        client = _client()
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request, patch(
            "domain_launch_assistant.domains.clients.namecom.time.sleep"
        ) as mock_sleep:
            mock_request.side_effect = [
                requests.Timeout("timed out"),
                _response(200, {"results": []}),
            ]
            results = client.check_availability(["ledgerflow.com"])

        assert results == []
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(0.5)  # backoff_base * 2**0

    def test_retries_on_5xx_then_succeeds(self):
        client = _client()
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request, patch(
            "domain_launch_assistant.domains.clients.namecom.time.sleep"
        ) as mock_sleep:
            mock_request.side_effect = [
                _response(503),
                _response(200, {"results": []}),
            ]
            results = client.check_availability(["ledgerflow.com"])

        assert results == []
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(0.5)

    def test_backoff_durations_are_exponential(self):
        client = _client(max_retries=3, retry_backoff_base=0.5)
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request, patch(
            "domain_launch_assistant.domains.clients.namecom.time.sleep"
        ) as mock_sleep:
            mock_request.side_effect = [
                requests.Timeout("timed out"),
                requests.Timeout("timed out"),
                _response(200, {"results": []}),
            ]
            client.check_availability(["ledgerflow.com"])

        assert mock_sleep.call_args_list == [
            ((0.5,),),
            ((1.0,),),
        ]

    def test_exhausts_retries_raises_timeout_error(self):
        client = _client(max_retries=3, retry_backoff_base=0.5)
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request, patch(
            "domain_launch_assistant.domains.clients.namecom.time.sleep"
        ) as mock_sleep:
            mock_request.side_effect = requests.Timeout("timed out")
            with pytest.raises(NameComTimeoutError):
                client.check_availability(["ledgerflow.com"])

        assert mock_request.call_count == 3
        assert mock_sleep.call_count == 2

    def test_exhausts_retries_raises_api_error_on_5xx(self):
        client = _client(max_retries=3, retry_backoff_base=0.5)
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request, patch(
            "domain_launch_assistant.domains.clients.namecom.time.sleep"
        ):
            mock_request.return_value = _response(500)
            with pytest.raises(NameComAPIError):
                client.check_availability(["ledgerflow.com"])

        assert mock_request.call_count == 3

    def test_4xx_never_retried(self):
        client = _client(max_retries=3, retry_backoff_base=0.5)
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request, patch(
            "domain_launch_assistant.domains.clients.namecom.time.sleep"
        ) as mock_sleep:
            mock_request.return_value = _response(400)
            with pytest.raises(NameComAPIError):
                client.check_availability(["ledgerflow.com"])

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()

    def test_connection_error_never_retried(self):
        """
        Only Timeout and 5xx are retried per spec — a bare
        ConnectionError (DNS failure, refused connection, etc.) fails
        immediately, same as before this wrapper existed.
        """
        client = _client(max_retries=3, retry_backoff_base=0.5)
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request, patch(
            "domain_launch_assistant.domains.clients.namecom.time.sleep"
        ) as mock_sleep:
            mock_request.side_effect = requests.ConnectionError("refused")
            with pytest.raises(NameComAPIError):
                client.check_availability(["ledgerflow.com"])

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()


class TestUpdateDomainPrivacy:
    def test_update_domain_privacy_success(self):
        client = _client()
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request:
            mock_request.return_value = _response(
                200, {"domainName": "ledgerflow.ai", "privacyEnabled": True}
            )
            result = client.update_domain_privacy("ledgerflow.ai", True)

        assert result == {"domainName": "ledgerflow.ai", "privacyEnabled": True}
        mock_request.assert_called_once_with(
            "PATCH",
            "https://api.dev.name.com/core/v1/domains/ledgerflow.ai",
            timeout=10,
            json={"privacyEnabled": True},
            auth=("u", "t"),
        )

    def test_update_domain_privacy_disable(self):
        client = _client()
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request:
            mock_request.return_value = _response(
                200, {"domainName": "ledgerflow.ai", "privacyEnabled": False}
            )
            result = client.update_domain_privacy("ledgerflow.ai", False)

        assert result["privacyEnabled"] is False
        _, kwargs = mock_request.call_args
        assert kwargs["json"] == {"privacyEnabled": False}

    def test_update_domain_privacy_409_conflict_raises(self):
        """
        Per name.com's docs, 409 here specifically means the domain/TLD
        doesn't support WHOIS privacy — a real, informative 4xx, never
        retried.
        """
        client = _client()
        with patch(
            "domain_launch_assistant.domains.clients.namecom.requests.request"
        ) as mock_request, patch(
            "domain_launch_assistant.domains.clients.namecom.time.sleep"
        ) as mock_sleep:
            mock_request.return_value = _response(409)
            with pytest.raises(NameComAPIError):
                client.update_domain_privacy("nopriv.tld", True)

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()