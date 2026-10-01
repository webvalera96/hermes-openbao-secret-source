# Proposal

## Why

Hermes Agent resolves provider credentials at process startup from external secret managers through its secret-source plugin API. Teams that standardize on OpenBao (the open-source, Vault-API-compatible secrets manager) currently have no supported way to hydrate Hermes environment variables from their KV store, forcing manual export of credentials. This change delivers a first-party-quality OpenBao secret-source plugin so operators can keep credentials in OpenBao and have Hermes resolve them automatically.

## What Changes

- Add a standalone Hermes secret-source plugin (`hermes-openbao-secret-source`, plugin name `openbao`) that resolves mapped env-var references from an OpenBao KV v2 mount.
- Implement the `SecretSource` contract: `name`, `label`, `shape = "mapped"`, `scheme = "openbao"`, `fetch()`, `is_enabled()`, `protected_env_vars()`, `config_schema()`, and `remediation()`.
- Authenticate with a static OpenBao/Vault token read from the configured token env var (`OPENBAO_TOKEN`, falling back to `VAULT_TOKEN`), with the token protected from override by any source.
- Resolve references of the form `openbao://<mount>/<path>#<key>` (or equivalent configured form) to a single environment variable value.
- Talk to OpenBao via the `hvac` Python library, using `OPENBAO_ADDR`/`VAULT_ADDR` for the server URL and configurable mount, namespace, and TLS options.
- Map failures to Hermes `ErrorKind` values (`NOT_CONFIGURED`, `AUTH_FAILED`, `AUTH_EXPIRED`, `REF_INVALID`, `NETWORK`, `EMPTY_VALUE`, `TIMEOUT`, `INTERNAL`) and `fetch()` never raises or prompts.
- Package the plugin with `uv` (`pyproject.toml`, lockfile) and a `plugin.yaml` manifest.
- Provide tests, including the Hermes `SecretSourceConformance` kit, plus a README with install and configuration instructions.

## Capabilities

### New Capabilities
- `openbao-secret-source`: Behavior of the Hermes secret-source plugin that resolves mapped environment variables from an OpenBao KV v2 mount, including configuration, token authentication, reference parsing, error mapping, provenance, and plugin registration.

### Modified Capabilities
<!-- No existing capabilities; this is a greenfield plugin with no prior specs. -->

## Impact

- **New repository content**: Python package under `src/hermes_openbao_secret_source/`, `plugin.yaml`, `pyproject.toml`, `uv.lock`, tests, and README.
- **External dependency**: `hvac` (Vault/OpenBao-compatible HTTP client). Runtime target is the Hermes Agent process; the plugin imports `agent.secret_sources.base`.
- **Interfaces**: Hermes `SecretSource` ABC, `FetchResult`, `ErrorKind`, and `SecretSourceConformance`.
- **Configuration surface**: `secrets.openbao.*` keys in Hermes config and the `OPENBAO_*`/`VAULT_*` environment variables.
- **No changes to Hermes core**: the plugin registers through the existing `register(ctx)` plugin entry point.
