# Tasks

## 1. Project scaffolding with uv

- [x] 1.1 Initialize the `uv` project: create `pyproject.toml` (PEP 621) with package name `hermes-openbao-secret-source`, `requires-python`, `hvac` runtime dependency, and `pytest` dev dependency; verify `uv sync` completes and creates `uv.lock`
- [x] 1.2 Create the `src/hermes_openbao_secret_source/` package with `__init__.py`, and `plugin.yaml` declaring `name: openbao` and a description; verify `uv run python -c "import hermes_openbao_secret_source"` succeeds and `plugin.yaml` parses as valid YAML with the expected keys
- [x] 1.3 Add `pyproject.toml` tooling config (pytest path, ruff if used) and verify `uv run pytest` runs (collecting zero tests is acceptable at this stage)

## 2. Configuration and reference parsing

- [x] 2.1 Implement config resolution: `enabled`, `addr` (from `OPENBAO_ADDR`/`VAULT_ADDR`), `mount` (default `secret`), `namespace`, `token_env` (default `OPENBAO_TOKEN`, fallback `VAULT_TOKEN`), `timeout_seconds` (default 120), `verify`, and `ca_cert`; verify with unit tests covering explicit config, environment fallbacks, and missing values
- [x] 2.2 Implement the reference parser for `openbao://<mount>/<path>#<key>`, rejecting refs that omit the mount or key or that contain ambiguous `#`/empty segments; verify with unit tests for valid refs and for malformed refs (including an omitted mount) that must yield `REF_INVALID`
- [x] 2.3 Implement mapping extraction that turns the configured `secrets` env-var map into parsed references and reports per-entry parse errors; verify with a unit test that a mixed map yields the valid entries plus `REF_INVALID` for the bad ones

## 3. OpenBao client and fetch core

- [x] 3.1 Implement the `hvac.Client` construction from resolved config (url, token, namespace, TLS `verify`/`ca_cert`) and a single KV v2 read helper returning the requested key's value; verify with unit tests using a mocked client that assert the correct `mount_point`/`path` arguments
- [x] 3.2 Implement `fetch()` orchestration: resolve refs independently, treat missing/empty keys as `EMPTY_VALUE`, and return `FetchResult.secrets` without touching `os.environ`; verify with unit tests for a successful multi-entry fetch and for a partially failing fetch
- [x] 3.3 Implement exception-to-`ErrorKind` mapping (`Unauthorized`/`Forbidden` -> `AUTH_FAILED`/`AUTH_EXPIRED`, `InvalidPath` -> `REF_INVALID`, connection/SSL -> `NETWORK`, timeout -> `TIMEOUT`, other -> `INTERNAL`) wrapped so `fetch()` never raises; verify with unit tests that raise each exception type from the mocked client and assert the resulting `error_kind`
- [x] 3.4 Implement the wall-clock timeout budget from `timeout_seconds` and verify with a test that a slow mocked read yields `TIMEOUT`
- [x] 3.5 Document all configuration keys, environment variables, and the reference grammar in `README.md`; verify every documented key is exercised by at least one test and the documented example ref parses — **superseded by `add-usage-documentation`**, which owns the README.

## 4. SecretSource contract hooks

- [x] 4.1 Implement `is_enabled()` (disabled unless `secrets.openbao.enabled` is true) and `fetch_timeout_seconds()`; verify with unit tests for enabled/disabled and the default budget
- [x] 4.2 Implement `protected_env_vars()` returning `token_env`, `OPENBAO_TOKEN`, and `VAULT_TOKEN`, and `override_existing()` behavior; verify with a unit test asserting the protected set and that a protected variable is not overwritten in an `apply_all()` round trip
- [x] 4.3 Implement `config_schema()` returning the non-secret supported keys and `remediation(kind, cfg)` as a pure, non-raising kind->hint mapping; verify with unit tests that `config_schema()` includes the documented keys and `remediation()` returns a hint for `AUTH_FAILED` and `""` for an unhandled kind without side effects
- [x] 4.4 Implement `register(ctx)` calling `ctx.register_secret_source(...)` and update `plugin.yaml`/package metadata if needed; verify with a unit test using a fake context that the source is registered with the expected `name`, `shape`, `scheme`, and `api_version`

## 5. Conformance tests and packaging docs

- [x] 5.1 Add a test that subclasses `tests.secret_sources.conformance.SecretSourceConformance` with this source and verify the full conformance suite passes
- [x] 5.2 Add an optional integration test (skipped unless an OpenBao dev address/token env flag is set) that reads a real KV v2 secret; verify it is skipped by default and passes against a dev OpenBao instance when enabled
- [x] 5.3 Complete `README.md` with installation via `uv`, `~/.hermes/plugins/openbao/` placement, a full `secrets.openbao` configuration example, precedence/provenance notes, and troubleshooting by `ErrorKind`; verify the documented configuration example is validated by a test — **superseded by `add-usage-documentation`**, which owns the README.

## 6. Integration validation

- [x] 6.1 Run the full test suite with `uv run pytest` and verify all tests pass, including unit, conformance, and registration tests
- [x] 6.2 Run `openspec validate add-openbao-secret-source --strict` and verify the change validates with no errors
