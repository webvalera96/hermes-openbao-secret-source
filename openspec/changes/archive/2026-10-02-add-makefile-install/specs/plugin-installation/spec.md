# Spec Delta

## Purpose

Provide a repeatable, cross-platform command surface for installing, removing, and verifying this plugin inside a local Hermes agent on macOS and Linux.

## ADDED Requirements

### Requirement: Configurable Hermes home
The installation tools SHALL resolve the target Hermes home from a `HERMES_HOME` variable, defaulting to `$(HOME)/.hermes` when unset, and SHALL place the plugin under `$(HERMES_HOME)/plugins/openbao`.

#### Scenario: Default Hermes home
- **WHEN** `HERMES_HOME` is unset
- **THEN** the target plugin directory resolves to `$HOME/.hermes/plugins/openbao`

#### Scenario: Custom Hermes home
- **WHEN** `HERMES_HOME` is set to a directory
- **THEN** the target plugin directory resolves to `$(HERMES_HOME)/plugins/openbao`

### Requirement: Install target
Running `make install` SHALL create the target plugin directory and copy the plugin package into it so that `plugin.yaml` and `__init__.py` sit side by side. Re-running install SHALL replace the existing copy so stale files from a prior version are not left behind.

#### Scenario: Installing into a fresh Hermes home
- **WHEN** no plugin exists at the target path and `make install` runs
- **THEN** `$(HERMES_HOME)/plugins/openbao/plugin.yaml` and `$(HERMES_HOME)/plugins/openbao/__init__.py` exist

#### Scenario: Re-installing over an existing copy
- **WHEN** the target directory already holds a previous version and `make install` runs
- **THEN** it holds the current package files and no files that were removed from the package

### Requirement: Uninstall target
Running `make uninstall` SHALL remove `$(HERMES_HOME)/plugins/openbao/` and SHALL exit successfully when the directory does not exist.

#### Scenario: Removing an installed plugin
- **WHEN** the plugin is installed and `make uninstall` runs
- **THEN** `$(HERMES_HOME)/plugins/openbao/` no longer exists

#### Scenario: Uninstalling when not installed
- **WHEN** the plugin is not installed and `make uninstall` runs
- **THEN** the command exits successfully without error

### Requirement: Verify target
Running `make verify` SHALL check that the plugin files are installed and that the plugin is activated in the Hermes configuration, and SHALL exit non-zero with a diagnostic naming the unmet condition. The file check tests for `plugin.yaml` and `__init__.py`. The activation check confirms `openbao` is under `plugins.enabled` and `secrets.openbao.enabled` is `true` in `$(HERMES_HOME)/config.yaml`; when that file is absent, it warns but does not fail.

#### Scenario: Verifying a successful installation
- **WHEN** the plugin files are present, `openbao` is listed under `plugins.enabled`, `secrets.openbao.enabled` is `true`, and `make verify` runs
- **THEN** the command reports success and exits zero

#### Scenario: Verifying a config with section-separator comments
- **WHEN** `openbao` is listed under `plugins.enabled` but a column-0 comment block sits between the section's keys and `make verify` runs
- **THEN** the command still finds the entry and reports success

#### Scenario: Verifying a missing installation
- **WHEN** the plugin directory or a required file is absent and `make verify` runs
- **THEN** the command prints a diagnostic naming the missing file and exits non-zero

#### Scenario: Verifying an installed but disabled plugin
- **WHEN** the plugin files are present but `openbao` is not listed under `plugins.enabled` and `make verify` runs
- **THEN** the command prints a diagnostic naming `plugins.enabled` and exits non-zero

#### Scenario: Verifying an enabled plugin with a disabled source
- **WHEN** `openbao` is listed under `plugins.enabled` but `secrets.openbao.enabled` is not `true` and `make verify` runs
- **THEN** the command prints a diagnostic naming `secrets.openbao.enabled` and exits non-zero

#### Scenario: Verifying before Hermes is configured
- **WHEN** `$(HERMES_HOME)/config.yaml` does not exist and `make verify` runs
- **THEN** the command prints a warning that the plugin is installed but unconfigured and exits zero

### Requirement: Cross-platform macOS and Linux support
The installation targets SHALL run under POSIX `sh` with `make` on both macOS and Linux, using only portable core utilities and no platform-specific flags. The plugin's Python dependency SHALL NOT be vendored; the Makefile SHALL leave runtime dependency installation to the operator's existing environment.

#### Scenario: Running on macOS
- **WHEN** `make install` runs on macOS
- **THEN** the install completes using only portable commands

#### Scenario: Running on Linux
- **WHEN** `make install` runs on Linux
- **THEN** the install completes using only portable commands

### Requirement: Discoverable targets
Invoking `make` with no target or `make help` SHALL list the available targets with short descriptions and SHALL not modify the filesystem.

#### Scenario: Default help
- **WHEN** `make` is run without a target
- **THEN** it prints the available targets and installs nothing
