"""Unit tests for fetch() orchestration, error mapping, and the timeout (tasks 3.2-3.4)."""

from __future__ import annotations

import os
import threading

import pytest
import requests
from hvac.exceptions import Forbidden, InvalidPath, Unauthorized

from agent.secret_sources.base import ErrorKind, FetchResult
from hermes_openbao_secret_source.client import EmptySecretValue
from hermes_openbao_secret_source.source import OpenBaoSource

from fakes import FakeClient, secret_response


class _StubSource(OpenBaoSource):
    """An OpenBao source whose hvac client is replaced by a test double."""

    def __init__(self, client):
        self._stub_client = client

    def _make_client(self, config):
        return self._stub_client


def _cfg(secrets, **overrides):
    cfg = {"enabled": True, "addr": "https://bao.example:8200", "secrets": secrets}
    cfg.update(overrides)
    return cfg


@pytest.fixture
def token(monkeypatch):
    """Provide a static token so fetch() gets past NOT_CONFIGURED."""
    monkeypatch.setenv("OPENBAO_TOKEN", "s.test-token")


def _echo_client(mapping):
    """A fake client keyed by ``(mount_point, path)`` returning ``{key: value}``."""

    def responder(*, path, mount_point):
        return secret_response(mapping[(mount_point, path)])

    return FakeClient(responder)


# --- task 3.2: orchestration ------------------------------------------------


def test_successful_multi_entry_fetch_returns_mapping_without_touching_environ(token, tmp_path):
    client = _echo_client(
        {
            ("secret", "team/llm"): {"api_key": "sk-1"},
            ("secret", "team/db"): {"password": "pw-1"},
        }
    )
    source = _StubSource(client)

    before = dict(os.environ)
    result = source.fetch(
        _cfg(
            {
                "OPENAI_API_KEY": "openbao://secret/team/llm#api_key",
                "DATABASE_PASSWORD": "openbao://secret/team/db#password",
            }
        ),
        tmp_path,
    )

    assert result.ok
    assert result.secrets == {"OPENAI_API_KEY": "sk-1", "DATABASE_PASSWORD": "pw-1"}
    assert os.environ == before
    assert client.v2.calls == [
        {"mount_point": "secret", "path": "team/llm"},
        {"mount_point": "secret", "path": "team/db"},
    ]


def test_reference_mount_selects_the_read_mount(token, tmp_path):
    client = _echo_client({("kv-prod", "team/llm"): {"api_key": "sk-prod"}})
    source = _StubSource(client)

    result = source.fetch(_cfg({"API_KEY": "openbao://kv-prod/team/llm#api_key"}), tmp_path)

    assert result.ok
    assert result.secrets == {"API_KEY": "sk-prod"}
    assert client.v2.calls == [{"mount_point": "kv-prod", "path": "team/llm"}]


def test_partial_failure_keeps_good_entry_and_warns(token, tmp_path):
    def responder(*, path, mount_point):
        if path == "team/missing":
            raise EmptySecretValue("key 'api_key' is absent from the secret")
        return secret_response({"api_key": "sk-ok"})

    source = _StubSource(FakeClient(responder))
    result = source.fetch(
        _cfg(
            {
                "GOOD_KEY": "openbao://secret/team/ok#api_key",
                "BAD_KEY": "openbao://secret/team/missing#api_key",
            }
        ),
        tmp_path,
    )

    assert result.ok
    assert result.secrets == {"GOOD_KEY": "sk-ok"}
    assert any("BAD_KEY" in warning for warning in result.warnings)


def test_invalid_reference_is_reported_and_other_entries_survive(token, tmp_path):
    source = _StubSource(_echo_client({("secret", "team/ok"): {"api_key": "sk-ok"}}))
    result = source.fetch(
        _cfg(
            {
                "GOOD_KEY": "openbao://secret/team/ok#api_key",
                "BAD_REF": "openbao:///team/ok#api_key",
            }
        ),
        tmp_path,
    )

    assert result.ok
    assert result.secrets == {"GOOD_KEY": "sk-ok"}
    assert any("BAD_REF" in warning for warning in result.warnings)


def test_only_invalid_reference_fails_with_ref_invalid(token, tmp_path):
    source = _StubSource(_echo_client({}))
    result = source.fetch(_cfg({"ONLY": "openbao:///team/ok#k"}), tmp_path)

    assert not result.ok
    assert result.error_kind is ErrorKind.REF_INVALID
    assert result.secrets == {}


def test_only_empty_value_fails_with_empty_value(token, tmp_path):
    source = _StubSource(FakeClient(lambda **_: secret_response({"k": ""})))
    result = source.fetch(_cfg({"ONLY": "openbao://secret/x#k"}), tmp_path)

    assert not result.ok
    assert result.error_kind is ErrorKind.EMPTY_VALUE
    assert result.secrets == {}


def test_missing_addr_is_not_configured(token, tmp_path):
    source = OpenBaoSource()
    result = source.fetch(_cfg({"A": "openbao://secret/x#k"}, addr=""), tmp_path)

    assert result.error_kind is ErrorKind.NOT_CONFIGURED
    assert result.secrets == {}


def test_missing_token_is_not_configured(tmp_path):
    source = OpenBaoSource()
    result = source.fetch(
        {"enabled": True, "addr": "https://bao:8200", "secrets": {"A": "openbao://secret/x#k"}},
        tmp_path,
    )

    assert result.error_kind is ErrorKind.NOT_CONFIGURED
    assert result.secrets == {}


def test_address_falls_back_to_env(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENBAO_TOKEN", "t")
    monkeypatch.setenv("OPENBAO_ADDR", "https://from-env:8200")
    seen: dict = {}

    class _RecordingSource(OpenBaoSource):
        def _make_client(self, config):
            seen["addr"] = config.addr
            return FakeClient(lambda **_: secret_response({"k": "v"}))

    result = _RecordingSource().fetch(
        {"enabled": True, "secrets": {"A": "openbao://secret/x#k"}}, tmp_path
    )

    assert result.ok
    assert seen["addr"] == "https://from-env:8200"


def test_token_falls_back_to_vault_token(monkeypatch, tmp_path):
    monkeypatch.setenv("VAULT_TOKEN", "vault-tok")
    seen: dict = {}

    class _RecordingSource(OpenBaoSource):
        def _make_client(self, config):
            seen["token"] = config.token
            return FakeClient(lambda **_: secret_response({"k": "v"}))

    result = _RecordingSource().fetch(
        {"enabled": True, "addr": "https://bao:8200", "secrets": {"A": "openbao://secret/x#k"}},
        tmp_path,
    )

    assert result.ok
    assert seen["token"] == "vault-tok"


# --- task 3.3: exception mapping + never raise ------------------------------


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (Unauthorized("bad token"), ErrorKind.AUTH_FAILED),
        (Forbidden("token expired"), ErrorKind.AUTH_EXPIRED),
        (InvalidPath("missing"), ErrorKind.REF_INVALID),
        (requests.exceptions.ConnectionError("down"), ErrorKind.NETWORK),
        (requests.exceptions.SSLError("tls"), ErrorKind.NETWORK),
        (requests.exceptions.ConnectTimeout("slow"), ErrorKind.TIMEOUT),
        (ValueError("unexpected"), ErrorKind.INTERNAL),
        (RuntimeError("boom"), ErrorKind.INTERNAL),
    ],
)
def test_client_exception_maps_to_error_kind(token, tmp_path, exc, expected):
    def responder(**_):
        raise exc

    source = _StubSource(FakeClient(responder))
    result = source.fetch(_cfg({"ONLY": "openbao://secret/x#k"}), tmp_path)

    assert isinstance(result, FetchResult)
    assert not result.ok
    assert result.error_kind is expected
    assert result.secrets == {}


def test_fetch_never_raises_on_malformed_config(tmp_path):
    source = OpenBaoSource()
    for cfg in (None, "nope", 42, [], {"enabled": True, "secrets": "not-a-map"}):
        result = source.fetch(cfg if isinstance(cfg, dict) else {}, tmp_path)
        assert isinstance(result, FetchResult)


def test_fetch_contains_client_construction_failure(token, tmp_path):
    class _BrokenSource(OpenBaoSource):
        def _make_client(self, config):
            raise RuntimeError("cannot build client")

    result = _BrokenSource().fetch(_cfg({"A": "openbao://secret/x#k"}), tmp_path)

    assert isinstance(result, FetchResult)
    assert not result.ok
    assert result.error_kind is ErrorKind.INTERNAL


# --- task 3.4: wall-clock timeout -------------------------------------------


def test_slow_read_yields_timeout(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENBAO_TOKEN", "t")
    released = threading.Event()

    def responder(**_):
        released.wait(5)  # block until the test releases us (5s safety valve)
        return secret_response({"k": "v"})

    source = _StubSource(FakeClient(responder))
    try:
        result = source.fetch(
            _cfg({"ONLY": "openbao://secret/x#k"}, timeout_seconds=0.2),
            tmp_path,
        )
    finally:
        released.set()

    assert not result.ok
    assert result.error_kind is ErrorKind.TIMEOUT
    assert result.secrets == {}
