# Proposal

## Why

Installing the plugin into a local Hermes agent currently means hand-copying `src/hermes_openbao_secret_source` into `~/.hermes/plugins/openbao`, as described in prose in the README. Operators on macOS and Linux have no single, repeatable command to install, upgrade, verify, or remove the plugin, and a manual copy can leave stale files, the wrong directory layout, or a missing `plugin.yaml`/`__init__.py` pair that Hermes silently fails to discover.

## What Changes

- Add a root `Makefile` that installs the plugin into a local Hermes agent on macOS and Linux.
- Provide targets:
  - `install` - copy the plugin package to `$(HERMES_HOME)/plugins/openbao/` so `plugin.yaml` and `__init__.py` sit side by side.
  - `uninstall` - remove `$(HERMES_HOME)/plugins/openbao/`.
  - `reinstall` - uninstall then install.
  - `verify` - confirm the installed manifest and module are present, and, when a Hermes configuration exists, that the plugin is enabled and the OpenBao source is switched on.
  - `help` - list available targets (default target).
- Make the Hermes home configurable via a `HERMES_HOME` variable that defaults to `$(HOME)/.hermes`.
- Work on macOS and Linux with POSIX `sh` and standard coreutils/BSD-compatible commands (`cp`, `rm`, `mkdir`, `test`), with no Linux-only flags.
- No runtime code, configuration keys, reference grammar, `plugin.yaml`, or packaging metadata change.

## Capabilities

### New Capabilities

- `plugin-installation`: the install/uninstall/verify contract a local operator uses to place this plugin into a Hermes agent on macOS and Linux.

### Modified Capabilities

- None.

## Impact

- **Repository content**: new root `Makefile`. README installation instructions are unchanged by this change (a later change may reference the Makefile).
- **Interfaces**: adds a developer/operator command surface only; the Hermes `SecretSource` contract, `secrets.openbao.*` configuration, and environment variables are untouched.
- **Dependencies**: none added or changed; the Makefile shells out only to `make`'s built-in tools.
- **Platforms**: macOS and Linux. Windows is out of scope.
- **Risk**: low - the change is additive tooling and touches no shipped runtime code.
