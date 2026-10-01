"""Unit tests for hvac client construction and KV v2 reads (task 3.1)."""

from __future__ import annotations

import pytest
import requests
from hvac.exceptions import Forbidden, InvalidPath, Unauthorized

from agent.secret_sources.base import ErrorKind
from hermes_openbao_secret_source.client import (
    EmptySecretValue,
    FetchDeadlineExceeded,
    _extract_key,
    build_client,
    classify_exception,
    read_kv_v2,
)
from hermes_openbao_secret_source.config import OpenBaoConfig

from fakes import FakeClient, secret_response


# --- build_client ----------------------------------------------------------


def test_build_client_forwards_url_token_and_verify(monkeypatch):
    import hvac

    captured: dict = {}

    class _RecordingClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(hvac, "Client", _RecordingClient)
    config = OpenBaoConfig(addr="https://bao.example:8200", token="s.abc", verify="/etc/ca.pem")

    client = build_client(config)

    assert isinstance(client, _RecordingClient)
    assert captured == {
        "url": "https://bao.example:8200",
        "token": "s.abc",
        "verify": "/etc/ca.pem",
    }
    assert "namespace" not in captured


def test_build_client_includes_namespace_only_when_set(monkeypatch):
    import hvac

    captured: dict = {}
    monkeypatch.setattr(hvac, "Client", lambda **kwargs: captured.update(kwargs) or "client")

    assert build_client(OpenBaoConfig(addr="https://bao", token="t", namespace="team-a")) == "client"
    assert captured["namespace"] == "team-a"


def test_build_client_passes_verify_false(monkeypatch):
    import hvac

    captured: dict = {}
    monkeypatch.setattr(hvac, "Client", lambda **kwargs: captured.update(kwargs) or "client")

    build_client(OpenBaoConfig(addr="https://bao", token="t", verify=False))
    assert captured["verify"] is False


# --- read_kv_v2 ------------------------------------------------------------


def test_read_kv_v2_asserts_mount_point_and_path_arguments():
    client = FakeClient(lambda **_: secret_response({"api_key": "sk-live"}))

    assert read_kv_v2(client, "kv-prod", "team/llm", "api_key") == "sk-live"
    assert client.v2.calls == [{"mount_point": "kv-prod", "path": "team/llm"}]


def test_read_kv_v2_propagates_client_exceptions():
    boom = RuntimeError("kaboom")

    def responder(**_):
        raise boom

    with pytest.raises(RuntimeError):
        read_kv_v2(FakeClient(responder), "secret", "x", "y")


# --- _extract_key ----------------------------------------------------------


@pytest.mark.parametrize(
    ("stored", "expected"),
    [("value", "value"), (42, "42"), (3.5, "3.5"), (True, "true"), (False, "false")],
)
def test_extract_key_coerces_scalars(stored, expected):
    assert _extract_key(secret_response({"k": stored}), "k") == expected


@pytest.mark.parametrize(
    ("response", "key"),
    [
        (secret_response({}), "k"),
        (secret_response({"k": None}), "k"),
        (secret_response({"k": ""}), "k"),
        (secret_response({"k": {"nested": 1}}), "k"),
        (secret_response({"k": [1, 2]}), "k"),
        ({"data": {}}, "k"),
        ({}, "k"),
        (None, "k"),
    ],
)
def test_extract_key_missing_or_empty_raises(response, key):
    with pytest.raises(EmptySecretValue):
        _extract_key(response, key)


# --- classify_exception ----------------------------------------------------


def test_classify_empty_value_and_timeouts():
    assert classify_exception(EmptySecretValue("x")) is ErrorKind.EMPTY_VALUE
    assert classify_exception(FetchDeadlineExceeded("x")) is ErrorKind.TIMEOUT
    assert classify_exception(requests.exceptions.ConnectTimeout("slow")) is ErrorKind.TIMEOUT


def test_classify_hvac_auth_errors():
    assert classify_exception(Unauthorized("bad token")) is ErrorKind.AUTH_FAILED
    assert classify_exception(Forbidden("permission denied")) is ErrorKind.AUTH_FAILED
    assert classify_exception(Forbidden("token expired")) is ErrorKind.AUTH_EXPIRED
    assert classify_exception(Unauthorized("Token is expired")) is ErrorKind.AUTH_EXPIRED


def test_classify_path_network_and_unexpected():
    assert classify_exception(InvalidPath("no such path")) is ErrorKind.REF_INVALID
    assert classify_exception(requests.exceptions.ConnectionError("down")) is ErrorKind.NETWORK
    assert classify_exception(requests.exceptions.SSLError("tls")) is ErrorKind.NETWORK
    assert classify_exception(ValueError("odd")) is ErrorKind.INTERNAL
