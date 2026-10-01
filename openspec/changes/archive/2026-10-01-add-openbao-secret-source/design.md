# Design

## Context

See `proposal.md` - Why. Key constraints from the Hermes secret-source API and the chosen scope:

- The plugin runs inside the Hermes Agent process and imports `agent.secret_sources.base` (`SecretSource`, `FetchResult`, `ErrorKind`, `run_secret_cli`).
- `fetch()` is the only startup-path entry point; it must be synchronous, never raise, and never prompt. The orchestrator (`apply_all`) owns all `os.environ` writes and precedence.
- The source is `mapped`-shaped: the user explicitly binds env-var names to references.
- Authentication is a static token (`OPENBAO_TOKEN`, falling back to `VAULT_TOKEN`); KV v2 is the only engine.
- The project is greenfield and uses `uv` for packaging and dependency management.

## Goals / Non-Goals

**Goals:**
- A standalone, installable Hermes plugin repo (`hermes-openbao-secret-source`, plugin name `openbao`) that a user can drop into `~/.hermes/plugins/openbao/`.
- A fully contract-compliant `SecretSource` backed by the `hvac` client.
- Predictable, machine-readable error reporting that maps OpenBao/hvac failures to Hermes `ErrorKind` values.
- A test suite that includes the Hermes `SecretSourceConformance` kit.

**Non-Goals:**
- No bulk/project-wide secret injection (mapped only, per scope).
- No KV v1 support.
- No AppRole/userpass/OIDC/Kubernetes authentication, and no token renewal or wrapping.
- No writes back to OpenBao and no changes to Hermes core.
- No interactive auth or CLI setup command in this change.

## Decisions

### D1: Use the `hvac` client over an HTTP client or the `bao` CLI
`hvac` is the de-facto Python client for the Vault API, which OpenBao implements. It handles KV v2 path construction (`secret/data/<path>`), namespaces, TLS options, and typed exceptions, avoiding a hand-rolled HTTP layer and the binary-install requirement of shelling out to `bao`.

- Alternatives: raw `httpx`/`requests` (more code, must reimplement KV v2 envelope and exception handling); `run_secret_cli()` against the `bao` CLI (requires the binary on every Hermes host, weaker for a "keep credentials in OpenBao" story where the client may run in a minimal container).
- Consequence: `hvac` becomes a pinned runtime dependency; OpenBao API compatibility is assumed (Vault-compatible by design).

### D2: Reference format `openbao://<mount>/<path>#<key>`
A single self-describing string per env var maximizes explicit intent and works with the `mapped` shape. The mount, path, and `#key` selector are all required: a reference that omits the mount or the `#key` selector, or that contains empty segments or an ambiguous `#`, is rejected as `REF_INVALID`. The `#key` selector identifies the field within the KV v2 secret, and the mount named in the reference is the mount the secret is read from.

- Alternatives: a table form (`path` + `key` as separate keys) is more verbose; dot/slash-only paths cannot express the key cleanly.
- The `scheme` field is declared `openbao` so the reference scheme is owned and validated by this source.

### D3: Resolution strategy - per-entry, partial-tolerant
Resolve each mapped entry independently. On a per-entry failure (invalid ref, missing/empty key) record the specific error and continue with the remaining entries, so one bad reference does not discard the whole result. Connection/auth failures are source-level and abort the fetch with a single error.

- Rationale: matches "mapped" semantics and the `EMPTY_VALUE` guidance (never apply `""` over a good credential).

### D4: Configuration keys and defaults
- `enabled` (bool, default false)
- `addr` (str; default from `OPENBAO_ADDR` then `VAULT_ADDR`)
- `mount` (str, default `secret`)
- `namespace` (str, optional)
- `token_env` (str, default `OPENBAO_TOKEN`)
- `timeout_seconds` (int, default 120)
- `verify` (bool|path, default true) and `ca_cert` (path, optional)
- `secrets` (map of `ENV_VAR -> openbao://...` reference)

`config_schema()` returns the non-secret keys for setup surfaces; the `secrets` map is user-authored and may be large, so it is declared as a free-form mapping.

### D5: Error mapping from hvac exceptions
Translate hvac exceptions in one place:
- `Unauthorized`/`Forbidden` -> `AUTH_FAILED` (or `AUTH_EXPIRED` when the response indicates an expired token)
- `InvalidPath` on a referenced path -> `REF_INVALID` (or `EMPTY_VALUE` when the path exists but the key is absent)
- `requests` connection/SSL errors -> `NETWORK`
- timeout (`requests.exceptions.Timeout` / wall-clock budget) -> `TIMEOUT`
- any other exception -> `INTERNAL`

A top-level `try/except` in `fetch()` guarantees the never-raise contract even for unanticipated failures.

### D6: Packaging with `uv`
Use a `pyproject.toml` (PEP 621) with `hvac` as a runtime dependency, dev dependencies for `pytest`, and a `uv.lock`. Package layout: `src/hermes_openbao_secret_source/` for `__init__.py` (the `SecretSource` + `register(ctx)`) plus `plugin.yaml` for the Hermes manifest. A `[project.entry-points]`-free, import-by-path plugin model matches Hermes' `~/.hermes/plugins/<name>/` discovery, so the distribution is installed/`uv sync`-ed and the plugin directory exposes `plugin.yaml` and `__init__.py`.

- Alternative: a `bao`-CLI-backed plugin with no Python deps (rejected in D1).

### D7: Testing
Unit-test reference parsing, config resolution, and error mapping with a mocked `hvac.Client` (no live server), and add a conformance test subclassing `tests.secret_sources.conformance.SecretSourceConformance`. Optionally add an integration test gated behind an env flag pointing at a dev OpenBao instance.

## Risks / Trade-offs

- [hvac may lag OpenBao-specific API changes] -> OpenBao keeps Vault API compatibility; pin `hvac` to a known-good range and document the tested version.
- [A broad `except Exception` could mask bugs] -> always set `error_kind = INTERNAL` and include a truncated message; log at debug for diagnosis.
- [Token in the process environment is readable by in-process code] -> inherent to Hermes' trust model and called out in the upstream docs; the source only reads the token and marks it protected.
- [Per-entry partial failure may surprise users expecting all-or-nothing] -> surface each error kind and rely on orchestrator warnings/provenance so the missing variables are visible.
- [Reference grammar collisions if `path` contains `#`] -> validate and reject ambiguous refs with `REF_INVALID`.

## Migration Plan

- New standalone repo; no data migration.
- Rollout: publish the package, document `uv` install and `~/.hermes/plugins/openbao/` placement, then enable via `secrets.openbao.enabled: true`.
- Rollback: set `enabled: false` (or remove the plugin directory); Hermes falls back to existing sources.

## Open Questions

- Whether a follow-up change should add AppRole authentication for production, non-static-token deployments.
- Whether to offer a KV v1 compatibility mode if users report legacy mounts.
