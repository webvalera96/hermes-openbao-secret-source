"""Optional live integration check against a dev OpenBao instance (task 5.2).

Skipped by default. To run it, export ``OPENBAO_INTEGRATION=1`` plus
``OPENBAO_ADDR`` and ``OPENBAO_TOKEN`` and point the mount/path/key at a KV v2
secret that already exists. The address/token are captured at collection time so
the suite's environment-isolation fixture cannot erase them.
"""

from __future__ import annotations

import os

import pytest

from hermes_openbao_secret_source.source import OpenBaoSource

_INTEGRATION_ENABLED = bool(os.environ.get("OPENBAO_INTEGRATION"))
_ADDR = os.environ.get("OPENBAO_ADDR", "")
_TOKEN = os.environ.get("OPENBAO_TOKEN", "")

pytestmark = pytest.mark.skipif(
    not _INTEGRATION_ENABLED,
    reason="set OPENBAO_INTEGRATION=1 (plus OPENBAO_ADDR/OPENBAO_TOKEN) to run the live check",
)


def test_reads_a_real_kv_v2_secret(tmp_path, monkeypatch):
    if not _ADDR or not _TOKEN:
        pytest.skip("OPENBAO_ADDR and OPENBAO_TOKEN are required")

    mount = os.environ.get("OPENBAO_INTEGRATION_MOUNT", "secret")
    path = os.environ.get("OPENBAO_INTEGRATION_PATH", "hermes/integration")
    key = os.environ.get("OPENBAO_INTEGRATION_KEY", "value")
    env_var = os.environ.get("OPENBAO_INTEGRATION_VAR", "OPENBAO_INTEGRATION_VALUE")

    monkeypatch.setenv("OPENBAO_TOKEN", _TOKEN)
    source = OpenBaoSource()

    result = source.fetch(
        {
            "enabled": True,
            "addr": _ADDR,
            "token_env": "OPENBAO_TOKEN",
            "secrets": {env_var: f"openbao://{mount}/{path}#{key}"},
        },
        tmp_path,
    )

    assert result.ok, result.error
    assert result.secrets.get(env_var)
