"""The OpenBao ``SecretSource`` and the plugin ``register`` entry point.

``fetch()`` is the only startup-path entry point. It resolves each mapped
reference independently, never writes to ``os.environ`` (the orchestrator owns
that), and never raises: every failure becomes a :class:`FetchResult` carrying a
machine-readable :class:`ErrorKind`.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any, FrozenSet, Optional

from agent.secret_sources.base import (
    SECRET_SOURCE_API_VERSION,
    ErrorKind,
    FetchResult,
    SecretSource,
)

from .client import (
    EmptySecretValue,
    FetchDeadlineExceeded,
    build_client,
    classify_exception,
    read_kv_v2,
)
from .config import (
    DEFAULT_MOUNT,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_TOKEN_ENV,
    FALLBACK_TOKEN_ENV,
    OpenBaoConfig,
    resolve_config,
    resolve_timeout_seconds,
)
from .refs import OpenBaoRef, extract_references

logger = logging.getLogger(__name__)


class OpenBaoSource(SecretSource):
    """Resolve mapped env vars from an OpenBao KV v2 mount."""

    api_version = SECRET_SOURCE_API_VERSION
    name = "openbao"
    label = "OpenBao"
    shape = "mapped"
    scheme = "openbao"
    token_env_key = "token_env"
    default_token_env = DEFAULT_TOKEN_ENV
    override_existing_default = False

    # -- SecretSource contract hooks --------------------------------------

    def is_enabled(self, cfg: dict) -> bool:
        """Enabled only when ``secrets.openbao.enabled`` is true."""
        return bool(isinstance(cfg, dict) and cfg.get("enabled"))

    def fetch_timeout_seconds(self, cfg: Any) -> float:
        """Wall-clock budget for one fetch; defaults to 120s, always positive."""
        return resolve_timeout_seconds(cfg if isinstance(cfg, dict) else {})

    def override_existing(self, cfg: Any) -> bool:
        """Gap-fill by default; only overwrite existing values when configured."""
        if isinstance(cfg, dict):
            return bool(cfg.get("override_existing", self.override_existing_default))
        return self.override_existing_default

    def protected_env_vars(self, cfg: dict) -> FrozenSet[str]:
        """Every token variable this source may read, so none can be overwritten."""
        return frozenset({self.token_env(cfg), DEFAULT_TOKEN_ENV, FALLBACK_TOKEN_ENV})

    def config_schema(self) -> dict:
        return {
            "enabled": {
                "description": "Master switch; the source is disabled until true.",
                "default": False,
            },
            "addr": {
                "description": "OpenBao server URL; falls back to OPENBAO_ADDR then VAULT_ADDR.",
                "default": "",
            },
            "mount": {
                "description": "Default KV v2 mount name (references name their own mount).",
                "default": DEFAULT_MOUNT,
            },
            "namespace": {
                "description": "OpenBao Enterprise namespace, if the server is namespaced.",
                "default": "",
            },
            "token_env": {
                "description": "Env var holding the static token; falls back to OPENBAO_TOKEN.",
                "default": DEFAULT_TOKEN_ENV,
            },
            "timeout_seconds": {
                "description": "Wall-clock fetch budget in seconds.",
                "default": int(DEFAULT_TIMEOUT_SECONDS),
            },
            "verify": {
                "description": "TLS verification: a boolean, or a CA bundle path.",
                "default": True,
            },
            "ca_cert": {
                "description": "Path to a CA certificate bundle (takes precedence over verify).",
                "default": "",
            },
            "override_existing": {
                "description": "Overwrite pre-existing .env/shell values (default: gap-fill).",
                "default": False,
            },
            "secrets": {
                "description": "Map of ENV_VAR to openbao://<mount>/<path>#<key> references.",
                "default": {},
            },
        }

    def remediation(self, kind: Optional[ErrorKind], cfg: dict) -> str:
        """One-line, side-effect-free hint for a failed fetch; "" when unhandled."""
        if kind is None:
            return ""
        token_env = self.token_env(cfg if isinstance(cfg, dict) else {})
        hints = {
            ErrorKind.NOT_CONFIGURED: (
                f"Set a token ({token_env} or VAULT_TOKEN) and a server address "
                "(addr, OPENBAO_ADDR, or VAULT_ADDR), then restart Hermes."
            ),
            ErrorKind.AUTH_FAILED: (
                f"OpenBao rejected the token in {token_env} - check it is valid and that its "
                "policies grant read access to the referenced mount/path."
            ),
            ErrorKind.AUTH_EXPIRED: (
                f"The token in {token_env} has expired - issue a fresh token and restart Hermes."
            ),
            ErrorKind.REF_INVALID: (
                "Rewrite the reference as openbao://<mount>/<path>#<key> with a non-empty "
                "mount, path, and key and no empty segments or extra '#'."
            ),
            ErrorKind.NETWORK: (
                "Check addr and network reachability; for TLS errors set verify/ca_cert correctly."
            ),
            ErrorKind.EMPTY_VALUE: (
                "Confirm the KV v2 secret and key exist and hold a non-empty value."
            ),
            ErrorKind.TIMEOUT: (
                "Raise secrets.openbao.timeout_seconds and check OpenBao server health and latency."
            ),
        }
        return hints.get(kind, "")

    # -- Fetch -------------------------------------------------------------

    def fetch(self, cfg: dict, home_path: Path) -> FetchResult:
        """Resolve mapped references; never raises, never prompts, never writes ``os.environ``."""
        result = FetchResult()
        try:
            config = resolve_config(cfg if isinstance(cfg, dict) else {})
            self._resolve(config, result)
        except Exception as exc:  # noqa: BLE001 - contract: fetch() never raises
            logger.debug("OpenBao fetch failed unexpectedly", exc_info=True)
            if result.error is None:
                result.fail(f"OpenBao fetch failed: {type(exc).__name__}: {exc}",
                            classify_exception(exc))
            else:
                result.secrets.clear()
        return result

    def _resolve(self, config: OpenBaoConfig, result: FetchResult) -> None:
        if not config.addr:
            result.fail(
                "secrets.openbao is enabled but no OpenBao address is configured "
                "(set addr, OPENBAO_ADDR, or VAULT_ADDR).",
                ErrorKind.NOT_CONFIGURED,
            )
            return
        if not config.token:
            result.fail(
                "secrets.openbao is enabled but no token is available "
                f"(set {config.token_env} or VAULT_TOKEN).",
                ErrorKind.NOT_CONFIGURED,
            )
            return

        entries, issues = extract_references(config.secrets)
        for issue in issues:
            result.warnings.append(f"{issue.env_var}: {issue.message}")
        if not entries:
            if issues:
                first = issues[0]
                result.fail(f"{first.env_var}: {first.message}", ErrorKind.REF_INVALID)
            return

        client = self._make_client(config)
        deadline = time.monotonic() + config.timeout_seconds
        entry_errors: list[tuple[ErrorKind, str]] = []

        for env_var, ref in entries:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result.secrets.clear()
                result.fail(f"OpenBao fetch exceeded {config.timeout_seconds:.0f}s budget",
                            ErrorKind.TIMEOUT)
                return
            try:
                value = self._read_with_deadline(client, ref, remaining)
            except FetchDeadlineExceeded:
                # Timeout is source-level: the whole result is discarded.
                result.secrets.clear()
                result.fail(f"OpenBao fetch exceeded {config.timeout_seconds:.0f}s budget",
                            ErrorKind.TIMEOUT)
                return
            except EmptySecretValue as exc:
                message = f"{env_var}: {exc}"
                entry_errors.append((ErrorKind.EMPTY_VALUE, message))
                result.warnings.append(message)
                continue
            except Exception as exc:  # noqa: BLE001
                kind = classify_exception(exc)
                if kind in (ErrorKind.REF_INVALID, ErrorKind.EMPTY_VALUE):
                    message = f"{env_var}: {exc}"
                    entry_errors.append((kind, message))
                    result.warnings.append(message)
                    continue
                # Connection/auth/other failures are source-level and abort the fetch.
                result.secrets.clear()
                result.fail(f"{env_var}: {exc}", kind)
                return
            result.secrets[env_var] = value

        if not result.secrets and entry_errors:
            kind, message = entry_errors[0]
            result.fail(message, kind)

    # -- Test seams --------------------------------------------------------

    def _make_client(self, config: OpenBaoConfig) -> Any:
        return build_client(config)

    def _read_with_deadline(self, client: Any, ref: OpenBaoRef, remaining: float) -> str:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="openbao-read")
        future = executor.submit(read_kv_v2, client, ref.mount, ref.path, ref.key)
        try:
            return future.result(timeout=remaining)
        except FuturesTimeoutError:
            future.cancel()
            raise FetchDeadlineExceeded(
                f"read of {ref.mount}/{ref.path}#{ref.key} timed out"
            ) from None
        finally:
            executor.shutdown(wait=False)


def register(ctx: Any) -> Any:
    """Hermes plugin entry point: register a single OpenBao secret source."""
    return ctx.register_secret_source(OpenBaoSource())
