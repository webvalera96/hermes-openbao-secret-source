"""Configuration resolution for the OpenBao secret source.

The ``cfg`` passed to :meth:`OpenBaoSource.fetch` is the raw
``secrets.openbao`` section and may be malformed, so every accessor is
defensive. Environment values are read through
:func:`agent.secret_sources.base.get_source_environment` (the per-fetch view)
so profile multiplexing cannot leak another profile's environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, Optional, Union

from agent.secret_sources.base import coerce_float, get_source_environment

DEFAULT_MOUNT = "secret"
DEFAULT_TOKEN_ENV = "OPENBAO_TOKEN"
FALLBACK_TOKEN_ENV = "VAULT_TOKEN"
ADDR_ENV_VARS = ("OPENBAO_ADDR", "VAULT_ADDR")
DEFAULT_TIMEOUT_SECONDS = 120.0

VerifySetting = Union[bool, str]


@dataclass(frozen=True)
class OpenBaoConfig:
    """Fully-resolved, immutable view of one ``secrets.openbao`` section."""

    enabled: bool = False
    addr: str = ""
    mount: str = DEFAULT_MOUNT
    namespace: str = ""
    token_env: str = DEFAULT_TOKEN_ENV
    token: str = ""
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    verify: VerifySetting = True
    secrets: Mapping[str, Any] = field(default_factory=dict)


def _as_mapping(cfg: Any) -> Mapping[str, Any]:
    return cfg if isinstance(cfg, Mapping) else {}


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def token_env_name(cfg: Any) -> str:
    """Name of the env var holding the bootstrap token (default ``OPENBAO_TOKEN``)."""
    configured = _clean(_as_mapping(cfg).get("token_env"))
    return configured or DEFAULT_TOKEN_ENV


def resolve_token(cfg: Any, environ: Optional[MutableMapping[str, str]] = None) -> str:
    """Token value: the configured token env var, falling back to ``VAULT_TOKEN``."""
    env = environ if environ is not None else get_source_environment()
    token = _clean(env.get(token_env_name(cfg), ""))
    if token:
        return token
    return _clean(env.get(FALLBACK_TOKEN_ENV, ""))


def resolve_addr(cfg: Any, environ: Optional[MutableMapping[str, str]] = None) -> str:
    """OpenBao address: ``addr`` config, then ``OPENBAO_ADDR``, then ``VAULT_ADDR``."""
    env = environ if environ is not None else get_source_environment()
    configured = _clean(_as_mapping(cfg).get("addr"))
    if configured:
        return configured
    for name in ADDR_ENV_VARS:
        value = _clean(env.get(name, ""))
        if value:
            return value
    return ""


def resolve_mount(cfg: Any) -> str:
    return _clean(_as_mapping(cfg).get("mount")) or DEFAULT_MOUNT


def _coerce_verify(value: Any, ca_cert: str) -> VerifySetting:
    if ca_cert:
        return ca_cert
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("false", "no", "0", "off"):
            return False
        if lowered in ("true", "yes", "1", "on"):
            return True
        if value.strip():
            return value.strip()
    return True


def resolve_verify(cfg: Any) -> VerifySetting:
    mapping = _as_mapping(cfg)
    ca_cert = _clean(mapping.get("ca_cert"))
    return _coerce_verify(mapping.get("verify", True), ca_cert)


def resolve_timeout_seconds(cfg: Any) -> float:
    value = coerce_float(_as_mapping(cfg).get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
                         DEFAULT_TIMEOUT_SECONDS)
    return value if value > 0 else DEFAULT_TIMEOUT_SECONDS


def resolve_secrets_map(cfg: Any) -> Mapping[str, Any]:
    """The ``secrets`` env-var -> reference map; ``{}`` when absent or malformed."""
    raw = _as_mapping(cfg).get("secrets")
    return raw if isinstance(raw, Mapping) else {}


def resolve_config(cfg: Any, environ: Optional[MutableMapping[str, str]] = None) -> OpenBaoConfig:
    mapping = _as_mapping(cfg)
    return OpenBaoConfig(
        enabled=bool(mapping.get("enabled")),
        addr=resolve_addr(mapping, environ),
        mount=resolve_mount(mapping),
        namespace=_clean(mapping.get("namespace")),
        token_env=token_env_name(mapping),
        token=resolve_token(mapping, environ),
        timeout_seconds=resolve_timeout_seconds(mapping),
        verify=resolve_verify(mapping),
        secrets=resolve_secrets_map(mapping),
    )
