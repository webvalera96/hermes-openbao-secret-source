"""Unit tests for the SecretSource contract hooks (tasks 4.1-4.4)."""

from __future__ import annotations

import pytest

from agent.secret_sources.base import SECRET_SOURCE_API_VERSION, ErrorKind
from hermes_openbao_secret_source.source import OpenBaoSource, register

from fakes import FakeClient, secret_response


# --- package surface --------------------------------------------------------


def test_package_lazily_exports_source_and_register():
    from hermes_openbao_secret_source import OpenBaoSource as ExportedSource
    from hermes_openbao_secret_source import register as exported_register

    assert ExportedSource is OpenBaoSource
    assert exported_register is register


# --- task 4.1: is_enabled + fetch_timeout_seconds ---------------------------


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        ({}, False),
        ({"enabled": False}, False),
        ({"enabled": True}, True),
        ({"enabled": "yes"}, True),
        (None, False),
        ("nope", False),
    ],
)
def test_is_enabled(cfg, expected):
    assert OpenBaoSource().is_enabled(cfg) is expected


def test_fetch_timeout_seconds_default_and_override():
    source = OpenBaoSource()

    assert source.fetch_timeout_seconds({"enabled": True}) == 120.0
    assert source.fetch_timeout_seconds({"timeout_seconds": 7}) == 7.0
    assert source.fetch_timeout_seconds({"timeout_seconds": "junk"}) == 120.0
    assert source.fetch_timeout_seconds({"timeout_seconds": 0}) == 120.0
    assert source.fetch_timeout_seconds(None) == 120.0


# --- task 4.2: protected_env_vars + override_existing -----------------------


def test_protected_env_vars_cover_every_token_variable():
    source = OpenBaoSource()

    assert source.protected_env_vars({"enabled": True}) == frozenset(
        {"OPENBAO_TOKEN", "VAULT_TOKEN"}
    )
    assert source.protected_env_vars({"token_env": "CUSTOM_TOKEN"}) == frozenset(
        {"CUSTOM_TOKEN", "OPENBAO_TOKEN", "VAULT_TOKEN"}
    )


def test_override_existing_defaults_to_false_and_can_be_enabled():
    source = OpenBaoSource()

    assert source.override_existing({}) is False
    assert source.override_existing({"override_existing": True}) is True
    assert source.override_existing(None) is False


def test_protected_token_variable_is_not_overwritten(monkeypatch, tmp_path):
    from agent.secret_sources import registry

    class _Stub(OpenBaoSource):
        def _make_client(self, config):
            return FakeClient(lambda **_: secret_response({"k": "from-openbao"}))

    registry._reset_registry_for_tests()
    monkeypatch.setattr(registry, "_ensure_builtin_sources", lambda: None)
    try:
        assert registry.register_source(_Stub())
        env = {"VAULT_TOKEN": "s.test-token"}
        report = registry.apply_all(
            {
                "openbao": {
                    "enabled": True,
                    "addr": "https://bao.example:8200",
                    "secrets": {
                        "OPENBAO_TOKEN": "openbao://secret/x#k",
                        "OTHER_VAR": "openbao://secret/x#k",
                    },
                }
            },
            tmp_path,
            environ=env,
        )
    finally:
        registry._reset_registry_for_tests()

    assert env["OTHER_VAR"] == "from-openbao"
    assert env["VAULT_TOKEN"] == "s.test-token"
    assert "OPENBAO_TOKEN" not in env
    source_report = next(sr for sr in report.sources if sr.name == "openbao")
    assert "OPENBAO_TOKEN" in source_report.skipped_protected


# --- task 4.3: config_schema + remediation ----------------------------------


def test_config_schema_lists_documented_keys():
    schema = OpenBaoSource().config_schema()

    for key in ("enabled", "addr", "mount", "namespace", "token_env",
                "timeout_seconds", "verify", "ca_cert", "override_existing", "secrets"):
        assert key in schema, f"config_schema() is missing {key!r}"
        assert "description" in schema[key]
        assert "default" in schema[key]


def test_remediation_auth_failed_hint_and_unhandled_kind():
    source = OpenBaoSource()

    hint = source.remediation(ErrorKind.AUTH_FAILED, {"enabled": True})
    assert isinstance(hint, str) and hint
    assert "token" in hint.lower()

    assert source.remediation(None, {}) == ""
    assert source.remediation(ErrorKind.BINARY_MISSING, {}) == ""


def test_remediation_never_raises_for_any_kind():
    source = OpenBaoSource()
    for kind in ErrorKind:
        assert isinstance(source.remediation(kind, {"token_env": "CUSTOM"}), str)


def test_remediation_does_not_mutate_config():
    source = OpenBaoSource()
    cfg = {"enabled": True, "token_env": "CUSTOM_TOKEN"}
    snapshot = dict(cfg)

    source.remediation(ErrorKind.AUTH_FAILED, cfg)

    assert cfg == snapshot


# --- task 4.4: register(ctx) ------------------------------------------------


class _FakeContext:
    def __init__(self) -> None:
        self.sources: list = []

    def register_secret_source(self, source):
        self.sources.append(source)
        return f"registered:{source.name}"


def test_register_registers_one_source_with_expected_identity():
    ctx = _FakeContext()

    outcome = register(ctx)

    assert outcome == "registered:openbao"
    assert len(ctx.sources) == 1
    source = ctx.sources[0]
    assert source.name == "openbao"
    assert source.label
    assert source.shape == "mapped"
    assert source.scheme == "openbao"
    assert source.api_version == SECRET_SOURCE_API_VERSION
