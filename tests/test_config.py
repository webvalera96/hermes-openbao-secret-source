"""Unit tests for configuration resolution (task 2.1)."""

from __future__ import annotations

import pytest

from hermes_openbao_secret_source.config import (
    DEFAULT_MOUNT,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_TOKEN_ENV,
    resolve_addr,
    resolve_config,
    resolve_mount,
    resolve_secrets_map,
    resolve_timeout_seconds,
    resolve_token,
    resolve_verify,
    token_env_name,
)


def test_explicit_config_is_used_verbatim():
    cfg = {
        "enabled": True,
        "addr": "https://openbao.example:8200",
        "mount": "kv-prod",
        "namespace": "team-a",
        "token_env": "MY_OPENBAO_TOKEN",
        "timeout_seconds": 15,
        "verify": False,
        "ca_cert": "/etc/ssl/ca.pem",
        "secrets": {"OPENAI_API_KEY": "openbao://kv-prod/team/llm#api_key"},
    }
    environ = {"MY_OPENBAO_TOKEN": "s.abc", "VAULT_TOKEN": "ignored"}
    resolved = resolve_config(cfg, environ)

    assert resolved.enabled is True
    assert resolved.addr == "https://openbao.example:8200"
    assert resolved.mount == "kv-prod"
    assert resolved.namespace == "team-a"
    assert resolved.token_env == "MY_OPENBAO_TOKEN"
    assert resolved.token == "s.abc"
    assert resolved.timeout_seconds == 15.0
    assert resolved.verify == "/etc/ssl/ca.pem"
    assert resolved.secrets == {"OPENAI_API_KEY": "openbao://kv-prod/team/llm#api_key"}


def test_addr_prefers_config_then_openbao_then_vault():
    assert resolve_addr({"addr": "https://cfg"}, {"OPENBAO_ADDR": "https://ob", "VAULT_ADDR": "https://v"}) == "https://cfg"
    assert resolve_addr({}, {"OPENBAO_ADDR": "https://ob", "VAULT_ADDR": "https://v"}) == "https://ob"
    assert resolve_addr({}, {"VAULT_ADDR": "https://v"}) == "https://v"
    assert resolve_addr({}, {}) == ""
    assert resolve_addr({"addr": "   "}, {"OPENBAO_ADDR": "https://ob"}) == "https://ob"


def test_token_env_default_and_override():
    assert token_env_name({}) == DEFAULT_TOKEN_ENV
    assert token_env_name({"token_env": "CUSTOM"}) == "CUSTOM"
    assert token_env_name({"token_env": "  "}) == DEFAULT_TOKEN_ENV


def test_token_primary_then_fallback_then_missing():
    assert resolve_token({}, {"OPENBAO_TOKEN": "primary", "VAULT_TOKEN": "fallback"}) == "primary"
    assert resolve_token({}, {"OPENBAO_TOKEN": "  ", "VAULT_TOKEN": "fallback"}) == "fallback"
    assert resolve_token({}, {"VAULT_TOKEN": "fallback"}) == "fallback"
    assert resolve_token({}, {}) == ""
    assert resolve_token({"token_env": "CUSTOM"}, {"CUSTOM": "x", "OPENBAO_TOKEN": "y"}) == "x"


def test_mount_default_and_override():
    assert resolve_mount({}) == DEFAULT_MOUNT
    assert resolve_mount({"mount": "team-kv"}) == "team-kv"
    assert resolve_mount({"mount": ""}) == DEFAULT_MOUNT


def test_timeout_default_override_and_garbage():
    assert resolve_timeout_seconds({}) == DEFAULT_TIMEOUT_SECONDS
    assert resolve_timeout_seconds({"timeout_seconds": 5}) == 5.0
    assert resolve_timeout_seconds({"timeout_seconds": "bogus"}) == DEFAULT_TIMEOUT_SECONDS
    assert resolve_timeout_seconds({"timeout_seconds": 0}) == DEFAULT_TIMEOUT_SECONDS
    assert resolve_timeout_seconds({"timeout_seconds": -3}) == DEFAULT_TIMEOUT_SECONDS


def test_verify_and_ca_cert():
    assert resolve_verify({}) is True
    assert resolve_verify({"verify": False}) is False
    assert resolve_verify({"verify": "false"}) is False
    assert resolve_verify({"verify": "/etc/ssl/ca.pem"}) == "/etc/ssl/ca.pem"
    assert resolve_verify({"verify": True, "ca_cert": "/ca.pem"}) == "/ca.pem"
    assert resolve_verify({"verify": "junk"}) == "junk"


def test_secrets_map_is_defensive():
    assert resolve_secrets_map({}) == {}
    assert resolve_secrets_map({"secrets": "not-a-map"}) == {}
    assert resolve_secrets_map({"secrets": ["a"]}) == {}
    assert resolve_secrets_map({"secrets": {"A": "b"}}) == {"A": "b"}


@pytest.mark.parametrize("cfg", [None, "not-a-dict", 42, [], {"enabled": True, "env": "bad"}])
def test_malformed_config_never_raises(cfg):
    resolved = resolve_config(cfg, {})
    assert resolved.mount == DEFAULT_MOUNT
    assert resolved.timeout_seconds == DEFAULT_TIMEOUT_SECONDS


def test_config_dict_is_not_mutated():
    cfg = {"enabled": True, "secrets": {"A": "openbao://secret/x#k"}}
    snapshot = dict(cfg)
    resolve_config(cfg, {})
    assert cfg == snapshot
