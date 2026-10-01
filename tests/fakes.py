"""Test doubles for the ``hvac`` client surface the OpenBao source uses.

The source only ever touches ``client.secrets.kv.v2.read_secret_version``, so a
tiny stand-in is enough: it records the arguments the source passed and returns
(or raises) whatever a test's ``responder`` decides.
"""

from __future__ import annotations

import types
from typing import Any, Callable


class FakeKvV2:
    """Records ``read_secret_version`` calls and delegates to ``responder``."""

    def __init__(self, responder: Callable[..., Any]) -> None:
        self._responder = responder
        self.calls: list[dict[str, str]] = []

    def read_secret_version(self, *, path: str, mount_point: str) -> Any:
        self.calls.append({"mount_point": mount_point, "path": path})
        return self._responder(path=path, mount_point=mount_point)


class FakeClient:
    """Minimal stand-in exposing ``client.secrets.kv.v2``."""

    def __init__(self, responder: Callable[..., Any]) -> None:
        self.v2 = FakeKvV2(responder)
        self.secrets = types.SimpleNamespace(kv=types.SimpleNamespace(v2=self.v2))


def secret_response(data: dict[str, Any]) -> dict[str, Any]:
    """Wrap ``{key: value}`` in the KV v2 read envelope."""
    return {"data": {"data": data}}
