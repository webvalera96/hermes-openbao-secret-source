# Design

## Context

See [`proposal.md`](openspec/changes/add-makefile-install/proposal.md) for motivation. The relevant current state:

- Hermes discovers native directory plugins at `~/.hermes/plugins/<name>/`, where `plugin.yaml` and `__init__.py` must sit side by side (see [`README.md`](README.md:56)).
- The shippable package is [`src/hermes_openbao_secret_source/`](src/hermes_openbao_secret_source) and contains `__init__.py`, `plugin.yaml`, and the runtime modules.
- The repository is managed with [`uv`](https://docs.astral.sh/uv/), and the only runtime dependency is `hvac>=2.0,<3` (see [`pyproject.toml`](pyproject.toml:10)).
- There is no build step: the plugin is installed by copying the source directory into the Hermes plugin directory.

The target operators use macOS and Linux with `make` already available.

## Goals / Non-Goals

**Goals:**

- One command to install, upgrade, verify, and remove the plugin for a local Hermes agent.
- Deterministic, idempotent install that leaves no stale files from a previous version.
- Portable across macOS (BSD userland) and Linux (GNU userland).

**Non-Goals:**

- Windows support.
- Installing or upgrading Python, `uv`, Hermes itself, or the `hvac` runtime dependency.
- Editing Hermes configuration (`secrets.openbao`) or managing tokens.
- Packaging a wheel/sdist or publishing to an index.

## Decisions

### Copy strategy: remove-then-copy instead of `rsync`

The `install` target deletes `$(HERMES_HOME)/plugins/openbao/` and re-copies the package directory via `cp -R`. This guarantees a clean tree with no files from a prior version, matching the "re-installing over an existing copy" scenario.

- **Why not `rsync --delete`:** `rsync` is not present by default on every minimal Linux image and its flag semantics differ across versions; `rm -rf` + `cp -R` is universally available and trivially portable.
- **Why not copy in place:** copying over an existing tree leaves renamed/removed files behind, which is exactly the failure the proposal calls out.

### Configurable root: `HERMES_HOME` with a `$(HOME)/.hermes` default

All targets derive `PLUGIN_DIR := $(HERMES_HOME)/plugins/openbao`, where `HERMES_HOME ?= $(HOME)/.hermes`, overridable from the environment or the command line (`make install HERMES_HOME=/opt/hermes`).

- **Why not hardcode `~/.hermes`:** CI, test harnesses, and operators with a non-default Hermes home need to redirect the install without editing the Makefile.
- **Alternative considered:** a separate `PREFIX`/`DESTDIR` scheme. Rejected as over-engineered; `HERMES_HOME` is the term Hermes itself uses.

### Runtime dependency is not vendored

The Makefile copies only the plugin package and documents that `hvac` is provided by the Hermes environment. It does not run `uv sync` or `pip install` on install.

- **Why:** install must not assume a particular Python environment or require network access, and a partial dependency install could leave Hermes in a worse state than a clear message. Dependency provisioning stays in the existing `uv`/`pip` workflow.
- **Alternative considered:** an `install-deps` target running `uv sync`. Deferred; the existing README workflow already covers it and mixing it into `install` would violate the non-goal above.

### Target set and phony declarations

Targets: `install`, `uninstall`, `reinstall`, `verify`, `help`, with `help` as the default (`.DEFAULT_GOAL := help`). All are declared `.PHONY` so a stray same-named file cannot shadow them. `verify` prints a diagnostic and exits non-zero for a missing manifest or module, making it usable as a post-install or CI check.

### `verify` checks activation, not just files

`verify` has two stages: a hard file check (manifest and module present) and an activation check that reads `$(HERMES_HOME)/config.yaml` for the two independent gates — `openbao` under `plugins.enabled` and `secrets.openbao.enabled: true`. It exits non-zero with a diagnostic naming the unmet gate.

- **Why:** file presence does not mean the plugin loads. Hermes plugins are opt-in via `plugins.enabled`, and the OpenBao source is inert until `secrets.openbao.enabled: true`; a file-only `verify` reports success for an installed-but-inactive plugin.
- **How:** the activation stage parses the config with POSIX `awk` (no new runtime dependency, preserving the "does not install Hermes or Python dependencies" non-goal). It supports the standard block YAML written by `hermes plugins enable` and `hermes config set`, and it skips comment and blank lines so a section-separator comment block between a section's keys does not close the block; inline/flow-map YAML is also matched for the single-value forms.
- **Absent config:** `verify` warns that the plugin is installed but unconfigured and still exits zero, so the cross-platform lifecycle checks on a bare temp `HERMES_HOME` (tasks 4.2-4.3) remain valid.

## Risks / Trade-offs

- **Runtime dependency drift** → The Makefile cannot guarantee `hvac` is importable in the Hermes environment. Mitigation: `verify` checks the installed files, and the README already documents the `hvac` requirement; a dependency check is out of scope here.
- **`rm -rf` on a mistyped `HERMES_HOME`** → `uninstall` and the install path derive from `$(HERMES_HOME)/plugins/openbao`; a wrong root deletes the wrong plugin directory. Mitigation: the path is fixed to the trailing `/plugins/openbao` segment, and `uninstall` is explicit rather than automatic.
- **Symlink/`cp -R` edge cases** → On macOS, `cp -R` on a symlinked plugin directory can behave unexpectedly. Mitigation: the remove-then-copy sequence makes the result a real directory on both platforms.
- **`cp -R src/hermes_openbao_secret_source ~/.hermes/plugins/openbao` vs copying contents** → Use `cp -R <src> <dest>` where `<dest>` does not pre-exist, so the package contents land directly in the plugin directory and `plugin.yaml`/`__init__.py` are side by side. The remove-first step guarantees `<dest>` is absent before the copy.
