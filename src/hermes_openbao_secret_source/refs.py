"""Reference parsing for the OpenBao secret source.

A mapped entry is an ``openbao://<mount>/<path>#<key>`` string. The mount, path,
and ``#<key>`` selector are all required: a reference that omits the mount or
the key, that uses a different scheme, or that contains empty path segments or
an ambiguous ``#`` is rejected as ``REF_INVALID``. The mount named in the
reference identifies the KV v2 mount the secret is read from.

:func:`extract_references` turns a configured ``secrets`` map into parsed
references plus per-entry errors, so one malformed entry never discards the
rest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from agent.secret_sources.base import ErrorKind

SCHEME = "openbao://"


class InvalidReference(ValueError):
    """A mapped value is not a well-formed ``openbao://`` reference."""


@dataclass(frozen=True)
class OpenBaoRef:
    """A parsed ``openbao://<mount>/<path>#<key>`` reference."""

    mount: str
    path: str
    key: str

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"{SCHEME}{self.mount}/{self.path}#{self.key}"


@dataclass(frozen=True)
class ReferenceIssue:
    """A per-entry parse failure, reported as ``REF_INVALID`` for that env var."""

    env_var: str
    message: str
    kind: ErrorKind = ErrorKind.REF_INVALID


def parse_reference(raw: Any) -> OpenBaoRef:
    """Parse one reference string, raising :class:`InvalidReference` when malformed."""
    if not isinstance(raw, str):
        raise InvalidReference("reference must be a string")
    text = raw.strip()
    if not text:
        raise InvalidReference("reference is empty")
    if not text.startswith(SCHEME):
        raise InvalidReference(f"reference must start with {SCHEME!r}")

    remainder = text[len(SCHEME):]
    if remainder.count("#") != 1:
        raise InvalidReference("reference must contain exactly one '#' before the key")
    location, _, key = remainder.partition("#")
    if not key or "/" in key:
        raise InvalidReference("reference key must be a non-empty field name")

    if "/" not in location:
        raise InvalidReference("reference must include a mount and a path")
    mount, _, path = location.partition("/")
    if not mount:
        raise InvalidReference("reference mount must not be empty")
    if not path or any(segment == "" for segment in path.split("/")):
        raise InvalidReference("reference path must not contain empty segments")

    return OpenBaoRef(mount=mount, path=path, key=key)


def extract_references(
    secrets: Any,
) -> Tuple[list[tuple[str, OpenBaoRef]], list[ReferenceIssue]]:
    """Split a ``secrets`` map into ``(valid_entries, issues)``.

    ``valid_entries`` preserves mapping order and pairs each env-var name with
    its parsed reference; ``issues`` carries an ``REF_INVALID`` record for every
    entry that could not be parsed.
    """
    valid: list[tuple[str, OpenBaoRef]] = []
    issues: list[ReferenceIssue] = []
    if not isinstance(secrets, Mapping):
        return valid, issues

    for env_var, raw in secrets.items():
        name = env_var if isinstance(env_var, str) else str(env_var)
        if not isinstance(env_var, str) or not env_var:
            issues.append(ReferenceIssue(name, "environment variable name must be a non-empty string"))
            continue
        try:
            ref = parse_reference(raw)
        except InvalidReference as exc:
            issues.append(ReferenceIssue(env_var, str(exc)))
            continue
        valid.append((env_var, ref))
    return valid, issues
