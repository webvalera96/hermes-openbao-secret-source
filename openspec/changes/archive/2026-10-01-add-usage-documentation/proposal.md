# Proposal

## Why

The repository currently ships a stub `README.md` that only links to the upstream Hermes Agent and OpenBao projects and states that full documentation is pending. Operators cannot learn how to install the plugin, enable it in Hermes, configure `secrets.openbao`, or write a valid `openbao://` reference without reading the source. For a plugin whose whole purpose is to let operators keep credentials in OpenBao, the absence of usage instructions blocks adoption and makes misconfiguration (missing token, wrong mount, bad reference) the default experience.

## What Changes

- Replace the stub `README.md` with complete, task-oriented usage documentation for the plugin, covering:
  - **Overview and prerequisites**: what the plugin does, the Hermes secret-source model, supported OpenBao KV v2, Python and Hermes runtime expectations.
  - **Installation**: obtaining the package and placing it where Hermes discovers plugins (`~/.hermes/plugins/openbao/`), including the `uv` workflow used by this repo.
  - **Enabling the source**: the `secrets.openbao.enabled: true` switch and the disabled-by-default behavior.
  - **Configuration reference**: every supported `secrets.openbao.*` key (`enabled`, `addr`, `mount`, `namespace`, `token_env`, `timeout_seconds`, `verify`, `ca_cert`, `secrets`) with type, default, and description, plus the environment variables (`OPENBAO_TOKEN`, `VAULT_TOKEN`, `OPENBAO_ADDR`, `VAULT_ADDR`).
  - **Reference grammar**: the `openbao://<mount>/<path>#<key>` form, mount defaulting, and rejected/ambiguous forms.
  - **Worked examples**: at least one complete `secrets.openbao` configuration block mapping real provider credentials, and a minimal single-variable example.
  - **Behavior notes**: fail-open `fetch()`, per-entry partial tolerance, protected token variables, timeouts, and orchestrator-owned precedence/provenance.
  - **Troubleshooting**: a table mapping each `ErrorKind` (`NOT_CONFIGURED`, `AUTH_FAILED`, `AUTH_EXPIRED`, `REF_INVALID`, `NETWORK`, `EMPTY_VALUE`, `TIMEOUT`, `INTERNAL`) to symptoms and fixes.
  - **Security notes**: static-token trust model and why the token variable is protected from override.
- Documentation is written in English (project context) and stays a single `README.md`; no separate `docs/` tree is introduced.
- No runtime code, configuration keys, reference grammar, or packaging metadata change.

### Relationship to in-flight work

The in-progress change `add-openbao-secret-source` also lists README work (tasks 3.5 and 5.3). This change owns the user-facing usage documentation as a single deliverable; whichever change lands second should reconcile so the README is authored once and remains consistent with the final implementation. This proposal assumes the config keys, reference grammar, and error kinds described above are the contract already specified in `add-openbao-secret-source`.

## Capabilities

### New Capabilities

<!-- Documentation-only change: no system behavior changes. Per OpenSpec guidance,
     specs describe behavior, so no delta spec is created and .openspec.yaml sets
     skip_specs: true. -->
- None. This is a documentation-only change with no spec-level behavior change.

### Modified Capabilities

- None.

## Impact

- **Repository content**: `README.md` only (full rewrite/expansion). No source files, tests, `plugin.yaml`, or `pyproject.toml` changes.
- **Interfaces**: documents, but does not alter, the Hermes `SecretSource` contract, the `secrets.openbao.*` configuration surface, the `OPENBAO_*`/`VAULT_*` environment variables, and the `ErrorKind` values.
- **Dependencies**: none added or changed.
- **Risk**: documentation drift if the implementation in `add-openbao-secret-source` changes after this README is written; mitigated by grounding every documented key and example in the plugin's own spec delta.
