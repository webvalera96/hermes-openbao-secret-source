# hermes-openbao-secret-source

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) secret-source plugin that
resolves mapped environment variables from an [OpenBao](https://openbao.org/) KV v2 mount.

Hermes resolves provider credentials at process startup from external secret managers. This
plugin lets operators keep credentials in OpenBao and reference them from Hermes configuration
instead of exporting them by hand.

## Table of contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Enable the source](#enable-the-source)
- [Quickstart](#quickstart)
- [Reference grammar](#reference-grammar)
- [Configuration reference](#configuration-reference)
- [Behavior notes](#behavior-notes)
- [Troubleshooting](#troubleshooting)
- [Security notes](#security-notes)

## Overview

`hermes-openbao-secret-source` is a Hermes secret-source plugin named `openbao`. It uses the
`mapped` shape: you explicitly bind an environment variable name to an OpenBao reference of the
form `openbao://<mount>/<path>#<key>`, and Hermes hydrates that variable at startup from the
value stored at the referenced KV v2 path.

Key properties:

- **Mapped by intent.** You choose exactly which variables are populated; the plugin never
  bulk-injects a whole mount.
- **Disabled by default.** Nothing is read from OpenBao until you set `secrets.openbao.enabled: true`.
- **Static token authentication.** The plugin authenticates with a token read from the
  environment (default `OPENBAO_TOKEN`, falling back to `VAULT_TOKEN`). No interactive prompts,
  AppRole, or OIDC are supported.
- **KV v2 only.** Secrets are read from an OpenBao/Vault KV version 2 mount.
- **Fail-open by contract.** `fetch()` never raises and never prompts: when OpenBao cannot be
  reached or a reference cannot be resolved, the plugin reports a machine-readable error and
  leaves the affected variables untouched, so a credential problem cannot crash startup.

## Prerequisites

- **Hermes Agent** with secret-source plugin support (the plugin registers with the
  `SECRET_SOURCE_API_VERSION` the runtime exposes).
- **Python 3.11-3.14** (see `requires-python` in `pyproject.toml`).
- **An OpenBao server** (or a Vault-API-compatible server) reachable from the Hermes host, with
  a KV version 2 mount. The default mount name is `secret`.
- **A static token** with read access to the referenced paths, exposed to the Hermes process via
  an environment variable (`OPENBAO_TOKEN` by default, or `VAULT_TOKEN` as a fallback).
- **`uv`** if you install from source (see below).

## Installation

The plugin is a native Hermes directory plugin: Hermes discovers it from
`~/.hermes/plugins/openbao/`, where `plugin.yaml` and `__init__.py` must sit side by side.

### From source with `uv`

The repository uses [`uv`](https://docs.astral.sh/uv/) for dependency management.

```bash
git clone https://github.com/<owner>/hermes-openbao-secret-source.git
cd hermes-openbao-secret-source
uv sync
```

Then place the package where Hermes discovers plugins:

```bash
mkdir -p ~/.hermes/plugins
cp -R src/hermes_openbao_secret_source ~/.hermes/plugins/openbao
```

After copying, Hermes finds the manifest at `~/.hermes/plugins/openbao/plugin.yaml` and the
module at `~/.hermes/plugins/openbao/__init__.py`.

### Verify the installation

Confirm the files landed where Hermes discovers plugins:

```bash
cat ~/.hermes/plugins/openbao/plugin.yaml
uv run python -c "import hermes_openbao_secret_source; print(hermes_openbao_secret_source.__version__)"
```

`make verify` performs the same file check and, when `$(HERMES_HOME)/config.yaml` exists, also
confirms both activation gates:

```bash
make verify                        # checks ~/.hermes/config.yaml
make verify HERMES_HOME=/opt/hermes
```

- `openbao` must be listed under `plugins.enabled` in `config.yaml` (Hermes plugins are opt-in).
- `secrets.openbao.enabled` must be `true`.

The target exits non-zero with a diagnostic naming the failing gate when either check fails. When
`config.yaml` does not exist yet, it reports the plugin as installed but not yet configured and exits
zero, so it can run before Hermes has been configured.

The plugin declares a single runtime dependency, `hvac>=2.0,<3`.

## Enable the source

The `openbao` source is disabled unless explicitly enabled. Add the following to the Hermes
configuration:

```yaml
secrets:
  openbao:
    enabled: true
```

While `enabled` is not `true`, the source reports itself as disabled and contributes no
environment variables.

The server address and token are read from the environment when not configured explicitly:

- **Token:** `OPENBAO_TOKEN`, falling back to `VAULT_TOKEN`.
- **Address:** `OPENBAO_ADDR`, falling back to `VAULT_ADDR`.

See the configuration reference for every supported key and environment variable.

## Quickstart

This minimal configuration resolves a single provider credential from OpenBao:

```yaml
secrets:
  openbao:
    enabled: true
    addr: "https://openbao.example:8200"
    secrets:
      OPENAI_API_KEY: "openbao://secret/team/llm#api_key"
```

Supply the token in the environment, then start Hermes as usual:

```bash
export OPENBAO_TOKEN="hvs.CAESIJEXAMPLE..."
hermes
```

In this example the plugin reads the `api_key` field from the KV v2 secret at
`secret/team/llm` on the configured server and exposes it to Hermes as `OPENAI_API_KEY`.

### Minimal single-variable variant

If the address and token are already provided through the environment, the configuration
reduces to:

```yaml
secrets:
  openbao:
    enabled: true
    secrets:
      OPENAI_API_KEY: "openbao://secret/team/llm#api_key"
```

## Reference grammar

A mapped value is an OpenBao reference of the form:

```
openbao://<mount>/<path>#<key>
```

| Part | Required | Meaning |
| --- | --- | --- |
| `openbao://` | yes | Scheme owned by this source. Only `openbao://` references are resolved. |
| `<mount>` | yes | Name of the KV v2 mount that holds the secret (for example `secret`). |
| `<path>` | yes | Path to the secret within the mount; it may contain multiple `/`-separated segments. |
| `#<key>` | yes | Field (key) to read from the KV v2 secret. |

Valid examples:

- `openbao://secret/team/llm#api_key` - mount `secret`, path `team/llm`, key `api_key`.
- `openbao://kv-prod/shared/providers#token` - mount `kv-prod`, path `shared/providers`, key `token`.

Both the mount and the `#<key>` selector are required. A reference that omits either is treated
as invalid, reported as `REF_INVALID` for that entry, and contributes no value for that
environment variable.

Rejected and ambiguous forms (each reported as `REF_INVALID`):

- Missing key selector: `openbao://secret/team/llm`
- Missing mount: `openbao:///team/llm#api_key`
- Empty path segment: `openbao://secret//llm#api_key`
- Ambiguous `#`: `openbao://secret/team#llm#api_key`
- Wrong scheme: `vault://secret/team/llm#api_key`

The `<mount>` in a reference belongs to the reference itself. The separate `mount` configuration
key (default `secret`) selects the KV v2 mount the source connects to; it does not make an
omitted mount valid inside a reference.

## Configuration reference

All keys live under `secrets.openbao` in the Hermes configuration. Configuration values are read
defensively: a malformed section never raises, and invalid values fall back to their defaults.

### `secrets.openbao` keys

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | bool | `false` | Whether the source participates in secret resolution. Must be `true` for any secret to be read. |
| `addr` | string | `""` | OpenBao server URL. When empty, `OPENBAO_ADDR` is used, then `VAULT_ADDR`. |
| `mount` | string | `secret` | Name of the KV v2 mount the source connects to. An empty value falls back to `secret`. |
| `namespace` | string | `""` | OpenBao Enterprise namespace, if the server is namespaced. |
| `token_env` | string | `OPENBAO_TOKEN` | Name of the environment variable that holds the static token. Falls back to `OPENBAO_TOKEN` when empty. |
| `timeout_seconds` | number | `120` | Wall-clock fetch budget in seconds. A non-numeric, zero, or negative value falls back to the default. |
| `verify` | bool or string | `true` | TLS verification. A boolean toggles verification; a string is treated as a CA bundle path. |
| `ca_cert` | string | `""` | Path to a CA certificate bundle. When set, it takes precedence over `verify`. |
| `secrets` | map | `{}` | Map of `ENV_VAR -> openbao://...` references. A non-map value is ignored and treated as empty. |

### Environment variables

| Variable | Purpose | Resolution order |
| --- | --- | --- |
| `OPENBAO_TOKEN` | Static token (primary). | Used first. Also the default value of `token_env`. |
| `VAULT_TOKEN` | Static token (fallback). | Used when the configured token variable (`OPENBAO_TOKEN` by default) is unset or empty. |
| `OPENBAO_ADDR` | OpenBao server URL (primary). | Used when `addr` is not configured. |
| `VAULT_ADDR` | OpenBao server URL (fallback). | Used when neither `addr` nor `OPENBAO_ADDR` is set. |

The token variables are protected from override by any secret source; see Security notes.

## Behavior notes

### Fail-open `fetch()`

`fetch()` never raises and never prompts, including for malformed configuration or unexpected
client errors. Failures are returned as a result carrying a machine-readable `ErrorKind` instead
of an exception, so a credential problem cannot abort Hermes startup.

- Authentication failures are reported as `AUTH_FAILED`.
- Unreachable servers or failed TLS handshakes are reported as `NETWORK`.
- Unexpected client exceptions are reported as `INTERNAL`.

Because the source reports errors rather than raising, startup continues with whatever
credentials were already available in the environment.

### Per-entry partial tolerance

Each entry in `secrets` is resolved independently. When a single entry fails, the source records
the specific error for that entry and continues with the remaining entries, so one bad reference
does not discard the whole result.

- An entry whose reference is invalid is reported as `REF_INVALID`.
- An entry whose key is absent or empty is reported as `EMPTY_VALUE`.

A failing entry produces no value, so it never replaces an existing credential with an empty
string.

### Protected token variables

The token environment variables the source may read (`token_env`, `OPENBAO_TOKEN`, and
`VAULT_TOKEN`) are reported through `protected_env_vars()`. No secret source, including this
one, may overwrite them, even if a mapping targets one of those names.

### Timeout budget

Every fetch is bounded by a wall-clock timeout, configured with `timeout_seconds` and defaulting
to 120 seconds. When OpenBao does not respond within the budget, the fetch is abandoned and
reported as `TIMEOUT`, and its result is discarded.

### Precedence and provenance (orchestrator-owned)

The plugin only returns the mapping of environment variables it would contribute. It never
writes to the process environment and never decides precedence: environment writes, source
ordering, mapped-versus-bulk precedence, first-claim-wins conflict handling, and provenance
labels all belong to the Hermes orchestrator.

- When a bulk source and this mapped source both claim the same variable, the orchestrator
  applies the mapped source's value.
- The orchestrator labels applied values with their origin, for example `(from <label>)`, in the
  startup output.

## Troubleshooting

Because `fetch()` is fail-open, a problem never aborts startup. Instead, the affected variables
are left at their existing values and the source reports a machine-readable `ErrorKind`. Use the
table below to map each kind to a symptom and a fix.

| `ErrorKind` | Symptom | Fix |
| --- | --- | --- |
| `NOT_CONFIGURED` | The source is enabled but contributes nothing: no token is available or no server URL is resolvable. | Set a token (`OPENBAO_TOKEN`, or `VAULT_TOKEN` as fallback) and a server URL (`addr`, `OPENBAO_ADDR`, or `VAULT_ADDR`). |
| `BINARY_MISSING` | A required OpenBao/Vault command-line executable cannot be found on `PATH` for a CLI-backed operation. | Install the required `bao` (or `vault`) CLI and put it on `PATH`. This plugin otherwise talks to OpenBao through the bundled `hvac` client and needs no binary. |
| `AUTH_FAILED` | OpenBao rejects the token as invalid or as lacking permission for the referenced path. | Check that the token is valid and that its policies grant read access to the mount/path; then update the token variable. Also confirm the `namespace`, if the server is namespaced. |
| `AUTH_EXPIRED` | OpenBao reports the token has expired. | Issue a fresh token and update the token environment variable; restart Hermes so the new value is read. |
| `REF_INVALID` | A specific mapped entry is skipped because its reference is malformed. | Rewrite the reference as `openbao://<mount>/<path>#<key>`; ensure it names a mount and includes the `#key` selector with no empty segments or extra `#`. |
| `NETWORK` | Connection refused, DNS failure, or a failed TLS handshake with the OpenBao server. | Verify `addr` and network reachability. For TLS problems, correct `verify`/`ca_cert` (for example, point `ca_cert` at the issuing CA). |
| `EMPTY_VALUE` | The referenced path or key returns no value, or an empty value. | Confirm the KV v2 secret exists at the path and that the key name is spelled correctly and holds a non-empty value. The existing environment value is preserved. |
| `TIMEOUT` | The fetch exceeded the wall-clock budget before OpenBao responded. | Increase `timeout_seconds`, and check server health, load, and network latency. |
| `INTERNAL` | An unexpected client error occurred while resolving secrets. | Inspect the plugin/Hermes logs for the recorded message; if it persists, report it with the log output. |

`REF_INVALID` and `EMPTY_VALUE` are per-entry: they affect only the entry that triggered them,
and the remaining entries still resolve. Every other kind - `NOT_CONFIGURED`, `BINARY_MISSING`,
`AUTH_FAILED`, `AUTH_EXPIRED`, `NETWORK`, `TIMEOUT`, and `INTERNAL` - is source-level and
aborts the fetch for all entries.

## Security notes

### Static-token trust model

The source authenticates to OpenBao with a static token read from the process environment. There
is no interactive prompt, token renewal, or token wrapping; the operator supplies the token.

- The token is only as trustworthy as the environment it is read from. Any code that can read
  the Hermes process environment can read the token, so keep that environment restricted and
  prefer short-lived tokens granted the narrowest read policy that still covers the referenced
  paths.
- The source is read-only toward OpenBao: it never writes secrets back, and it never writes to
  the process environment itself. It returns the mapping it would contribute, and the orchestrator
  applies it.

### Why token variables are protected

The source reports the token variables it may read (`token_env`, `OPENBAO_TOKEN`, and
`VAULT_TOKEN`) through `protected_env_vars()`.

- Protecting them prevents any secret source - including this one - from overwriting the
  credential used to authenticate to OpenBao. Without this protection, a resolved secret whose
  target name collided with a token variable could silently replace the bootstrap token or mask a
  misconfiguration.
- Because the token is bootstrap material rather than a secret to be resolved, the orchestrator
  refuses to let any source write to these names.
