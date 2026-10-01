"""Hermes Agent secret-source plugin for OpenBao.

Resolves mapped environment variables from an OpenBao (Vault API compatible)
KV v2 mount through the Hermes ``SecretSource`` contract. The public entry
point is :func:`register`, which Hermes calls during plugin discovery.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"

__all__ = ["OpenBaoSource", "register", "__version__"]


def __getattr__(name: str) -> Any:
    """Expose the plugin surface lazily.

    Importing :mod:`hermes_openbao_secret_source` must not require the Hermes
    runtime (``agent.secret_sources.base``) until a caller actually asks for the
    source or the entry point, so the package stays importable standalone.
    """
    if name in ("OpenBaoSource", "register"):
        from . import source

        return getattr(source, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
