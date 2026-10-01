# openbao-secret-source Specification

## Purpose

Resolve Hermes Agent environment variables from an OpenBao KV v2 mount through the Hermes secret-source plugin interface, so operators can keep provider credentials in OpenBao instead of exporting them manually.

## Requirements

### Requirement: Plugin identity and registration
The plugin SHALL expose an OpenBao secret source that registers with Hermes through `ctx.register_secret_source()` and declares `name = "openbao"`, a human-readable `label`, `shape = "mapped"`, the URI `scheme = "openbao"`, and an `api_version` equal to the current `SECRET_SOURCE_API_VERSION`.

#### Scenario: Registering the source
- **WHEN** Hermes performs plugin discovery and calls the plugin's `register(ctx)`
- **THEN** a single OpenBao secret source is registered under the name `openbao` with shape `mapped` and scheme `openbao`

#### Scenario: Rejecting an invalid registration target
- **WHEN** the plugin registers against a Hermes runtime whose `SECRET_SOURCE_API_VERSION` differs from the version the plugin targets
- **THEN** the registry skips the source with a warning instead of crashing startup

### Requirement: Disabled-by-default enablement
The source SHALL be disabled unless explicitly enabled through configuration, and SHALL report enablement via `is_enabled(cfg)`, which returns true only when `secrets.openbao.enabled` is true.

#### Scenario: Not enabled
- **WHEN** the configuration does not set `secrets.openbao.enabled: true`
- **THEN** `is_enabled()` returns false and the source contributes no environment variables

#### Scenario: Enabled explicitly
- **WHEN** the configuration sets `secrets.openbao.enabled: true`
- **THEN** `is_enabled()` returns true and the source participates in the post-discovery secret re-pull

### Requirement: Static token authentication
The source SHALL authenticate to OpenBao with a static token read from the environment variable named by the configuration key `token_env`, defaulting to `OPENBAO_TOKEN`, and SHALL fall back to `VAULT_TOKEN` when the primary variable is unset or empty.

#### Scenario: Primary token variable present
- **WHEN** `OPENBAO_TOKEN` is set to a non-empty value
- **THEN** the source uses that token for OpenBao requests

#### Scenario: Fallback token variable used
- **WHEN** `OPENBAO_TOKEN` is unset or empty and `VAULT_TOKEN` is set
- **THEN** the source uses `VAULT_TOKEN` for OpenBao requests

#### Scenario: No token available
- **WHEN** neither the primary nor fallback token variable provides a non-empty value
- **THEN** `fetch()` returns an error with kind `NOT_CONFIGURED` and applies no secrets

### Requirement: Token is protected from override
The source SHALL report every token environment variable it may read (`token_env`, `OPENBAO_TOKEN`, and `VAULT_TOKEN`) through `protected_env_vars()` so that no secret source, including this one, can overwrite them.

#### Scenario: Protected token
- **WHEN** the orchestrator applies resolved secrets and a secret would target a protected token variable
- **THEN** the protected variable is not overwritten

### Requirement: OpenBao connection configuration
The source SHALL determine the OpenBao server URL from the configuration key `addr`, defaulting to `OPENBAO_ADDR` and then `VAULT_ADDR`, and SHALL support optional `namespace`, `mount` (default `secret`), and TLS verification settings (`verify` and `ca_cert`).

#### Scenario: Address from environment
- **WHEN** `addr` is not set in configuration and `OPENBAO_ADDR` or `VAULT_ADDR` is set
- **THEN** the source uses that value as the OpenBao server URL

#### Scenario: Missing address
- **WHEN** the source is enabled but no server URL is resolvable
- **THEN** `fetch()` returns an error with kind `NOT_CONFIGURED` and applies no secrets

#### Scenario: Custom mount and namespace
- **WHEN** configuration sets `mount` and `namespace`
- **THEN** the source reads secrets from the configured KV v2 mount within the configured namespace

### Requirement: Mapped reference resolution
The source SHALL resolve each configured env-var entry to a value read from an OpenBao KV v2 path, where a reference has the form `openbao://<mount>/<path>#<key>`, and SHALL return a mapping of environment variable names to secret values from `fetch()` without writing to `os.environ`.

#### Scenario: Successful mapped fetch
- **WHEN** configuration maps `OPENAI_API_KEY` to `openbao://secret/team/llm#api_key` and OpenBao returns a non-empty value for that key
- **THEN** `fetch()` returns a result containing `OPENAI_API_KEY` mapped to that value

#### Scenario: Reference omits mount
- **WHEN** a reference omits the mount or the `#key` selector
- **THEN** the source treats the reference as invalid, reports kind `REF_INVALID` for that entry, and applies no value for it

#### Scenario: Requested key absent or empty
- **WHEN** OpenBao returns no value, or an empty value, for a referenced key while an existing credential is present
- **THEN** the source reports kind `EMPTY_VALUE` and does not produce an empty value for that variable

### Requirement: Error mapping and fail-open behavior
The source SHALL map failures to machine-readable `ErrorKind` values (`NOT_CONFIGURED`, `BINARY_MISSING`, `AUTH_FAILED`, `AUTH_EXPIRED`, `REF_INVALID`, `NETWORK`, `EMPTY_VALUE`, `TIMEOUT`, `INTERNAL`), SHALL never raise from `fetch()`, and SHALL never prompt for input during startup.

#### Scenario: Authentication failure
- **WHEN** OpenBao rejects the token
- **THEN** `fetch()` returns an error with kind `AUTH_FAILED` and does not raise

#### Scenario: Connection failure
- **WHEN** the OpenBao server is unreachable or the TLS handshake fails
- **THEN** `fetch()` returns an error with kind `NETWORK` and does not raise

#### Scenario: Unexpected failure
- **WHEN** the hvac client raises an unexpected exception while resolving secrets
- **THEN** `fetch()` returns an error with kind `INTERNAL` and does not raise

#### Scenario: Non-interactive execution
- **WHEN** `fetch()` runs in a non-TTY context such as a gateway, cron, or container process
- **THEN** it completes without prompting or blocking on standard input

### Requirement: Fetch timeout budget
The source SHALL bound each fetch by a wall-clock timeout, defaulting to 120 seconds and overridable through the `timeout_seconds` configuration key, and SHALL report kind `TIMEOUT` when the budget is exceeded.

#### Scenario: Default budget
- **WHEN** `timeout_seconds` is not configured
- **THEN** `fetch_timeout_seconds(cfg)` returns a positive value of 120 seconds

#### Scenario: Exceeding the budget
- **WHEN** OpenBao does not respond within the configured timeout
- **THEN** `fetch()` returns an error with kind `TIMEOUT` and its result is discarded

### Requirement: Conflict precedence and provenance
The source SHALL leave environment writes, source ordering, mapped-vs-bulk precedence, first-claim-wins conflict handling, and provenance labeling to the Hermes orchestrator, and SHALL only return the mapping it would contribute.

#### Scenario: Contested variable
- **WHEN** a bulk source and this mapped source both claim the same variable
- **THEN** the orchestrator applies the mapped source's value and the startup output labels it `(from <label>)`

### Requirement: Configuration schema and remediation
The source SHALL declare its supported configuration keys through `config_schema()` and SHALL provide a pure, non-raising `remediation(kind, cfg)` mapping that returns setup hints for the relevant `ErrorKind` values and an empty string when no hint applies.

#### Scenario: Declaring configuration keys
- **WHEN** a setup surface calls `config_schema()`
- **THEN** it returns the supported keys, including `enabled`, `addr`, `mount`, `namespace`, `token_env`, `timeout_seconds`, and `verify`

#### Scenario: Remediation hint for auth failure
- **WHEN** `remediation(ErrorKind.AUTH_FAILED, cfg)` is called
- **THEN** it returns a non-empty hint describing how to provide a valid OpenBao token

#### Scenario: Remediation is side-effect free
- **WHEN** `remediation()` is called for any error kind
- **THEN** it performs no I/O and never raises

### Requirement: SecretSource contract conformance
The source SHALL satisfy the Hermes `SecretSourceConformance` kit, including never-raising on malformed configuration, machine-readable error kinds, disabled-by-default behavior, positive timeouts, valid protected-variable names, and a full `apply_all()` round trip.

#### Scenario: Conformance suite passes
- **WHEN** the plugin's test suite subclasses `SecretSourceConformance` with this source
- **THEN** all conformance checks pass
