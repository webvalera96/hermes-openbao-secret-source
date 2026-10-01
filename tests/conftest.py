"""Shared pytest configuration.

The plugin targets the Hermes ``agent.secret_sources`` contract, which is not a
PyPI dependency: it is supplied by the Hermes Agent runtime. Tests import the
real contract (and the ``tests.secret_sources.conformance`` kit) from a Hermes
checkout. Set ``HERMES_AGENT_REPO`` to point at one; otherwise the default
``~/.hermes/hermes-agent`` checkout is used.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_DEFAULT_HERMES_REPO = Path.home() / ".hermes" / "hermes-agent"

# Ambient shell values that would make fetch() tests non-deterministic.
_OPENBAO_ENV_VARS = ("OPENBAO_ADDR", "VAULT_ADDR", "OPENBAO_TOKEN", "VAULT_TOKEN")


def _ensure_hermes_on_path() -> None:
    try:
        import agent.secret_sources.base  # noqa: F401

        return
    except Exception:
        pass

    candidates = []
    override = os.environ.get("HERMES_AGENT_REPO")
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(_DEFAULT_HERMES_REPO)

    for candidate in candidates:
        if (candidate / "agent" / "secret_sources" / "base.py").is_file():
            sys.path.insert(0, str(candidate))
            return


_ensure_hermes_on_path()


@pytest.fixture(autouse=True)
def _isolate_openbao_environment(monkeypatch):
    """Keep the developer's shell from leaking OpenBao settings into tests."""
    for name in _OPENBAO_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    yield
