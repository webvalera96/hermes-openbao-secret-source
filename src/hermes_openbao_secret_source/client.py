"""OpenBao access: hvac client construction, KV v2 reads, exception mapping.

The source talks to OpenBao through the ``hvac`` client, which implements the
Vault/OpenBao KV v2 API (path ``<mount>/data/<path>``), namespaces, and TLS
options. Failures are translated to Hermes :class:`ErrorKind` values in one
place so the fetch loop can report machine-readable outcomes.
"""

from __future__ import annotations

from typing import Any, Mapping

from agent.secret_sources.base import ErrorKind

from .config import OpenBaoConfig


class EmptySecretValue(Exception):
    """The KV v2 path exists but the requested key is absent or empty."""


class FetchDeadlineExceeded(Exception):
    """The wall-clock fetch budget elapsed before a read returned."""


def build_client(config: OpenBaoConfig) -> Any:
    """Construct an ``hvac.Client`` from resolved configuration."""
    import hvac

    params: dict[str, Any] = {
        "url": config.addr,
        "token": config.token,
        "verify": config.verify,
    }
    if config.namespace:
        params["namespace"] = config.namespace
    return hvac.Client(**params)


def read_kv_v2(client: Any, mount: str, path: str, key: str) -> str:
    """Read one key from a KV v2 secret, raising :class:`EmptySecretValue` when absent.

    hvac raises ``InvalidPath`` (mapped to ``REF_INVALID``) for a missing path;
    the ``#key`` selector is applied here against the returned secret data.
    """
    response = client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount)
    return _extract_key(response, key)


def _extract_key(response: Any, key: str) -> str:
    payload = response.get("data") if isinstance(response, Mapping) else None
    data = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(data, Mapping) or key not in data:
        raise EmptySecretValue(f"key {key!r} is absent from the secret")
    value = data[key]
    if value is None:
        raise EmptySecretValue(f"key {key!r} has no value")
    if isinstance(value, str):
        if value == "":
            raise EmptySecretValue(f"key {key!r} is empty")
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    raise EmptySecretValue(f"key {key!r} does not hold a scalar value")


def classify_exception(exc: BaseException) -> ErrorKind:
    """Map an exception raised while resolving secrets onto the ``ErrorKind`` taxonomy."""
    if isinstance(exc, EmptySecretValue):
        return ErrorKind.EMPTY_VALUE
    if isinstance(exc, FetchDeadlineExceeded):
        return ErrorKind.TIMEOUT

    import requests

    if isinstance(exc, requests.exceptions.Timeout):
        return ErrorKind.TIMEOUT

    try:
        from hvac.exceptions import Forbidden, InvalidPath, Unauthorized
    except Exception:  # pragma: no cover - hvac is a declared runtime dependency
        class _Never:
            pass

        Forbidden = InvalidPath = Unauthorized = _Never

    message = str(exc).lower()
    if isinstance(exc, (Unauthorized, Forbidden)):
        return ErrorKind.AUTH_EXPIRED if "expired" in message else ErrorKind.AUTH_FAILED
    if isinstance(exc, InvalidPath):
        return ErrorKind.REF_INVALID
    if isinstance(exc, requests.exceptions.RequestException):
        return ErrorKind.NETWORK
    return ErrorKind.INTERNAL
