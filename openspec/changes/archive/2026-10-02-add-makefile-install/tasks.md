# Tasks

## 1. Makefile foundation

- [x] 1.1 Add a root `Makefile` with `HERMES_HOME ?= $(HOME)/.hermes`, derived `PLUGIN_DIR := $(HERMES_HOME)/plugins/openbao`, and a `SCRIPT_SRC := src/hermes_openbao_secret_source` variable. Verify with `make -n install` that `PLUGIN_DIR` expands to `$(HOME)/.hermes/plugins/openbao`, and again with `make -n install HERMES_HOME=/tmp/h`.
- [x] 1.2 Declare `.PHONY` for every target and set `.DEFAULT_GOAL := help`, then add a `help` target that prints the target list. Verify `make` and `make help` print the targets and exit zero, and that `test ! -e ~/.hermes/plugins/openbao` holds afterward (no filesystem change).

## 2. Install and uninstall

- [x] 2.1 Implement `install`: create `$(PLUGIN_DIR)`'s parent with `mkdir -p`, remove any existing `$(PLUGIN_DIR)` with `rm -rf`, then `cp -R $(SCRIPT_SRC) $(PLUGIN_DIR)`. Verify `make install HERMES_HOME=/tmp/h1` leaves `/tmp/h1/plugins/openbao/plugin.yaml` and `/tmp/h1/plugins/openbao/__init__.py` side by side.
- [x] 2.2 Add a stale-file check: create `/tmp/h2/plugins/openbao/LEGACY` before `make install HERMES_HOME=/tmp/h2` and verify `/tmp/h2/plugins/openbao/LEGACY` no longer exists after install (idempotent refresh).
- [x] 2.3 Implement `uninstall` as `rm -rf $(PLUGIN_DIR)`. Verify `make uninstall HERMES_HOME=/tmp/h1` removes `/tmp/h1/plugins/openbao`, and that a second `make uninstall HERMES_HOME=/tmp/h1` still exits zero when the directory is absent.
- [x] 2.4 Implement `reinstall` as `uninstall` followed by `install`. Verify `make reinstall HERMES_HOME=/tmp/h1` ends with the plugin present and exits zero.

## 3. Verify target

- [x] 3.1 Implement `verify` to test for `$(PLUGIN_DIR)/plugin.yaml` and `$(PLUGIN_DIR)/__init__.py`, print a success message and exit zero when both exist. Verify `make verify HERMES_HOME=/tmp/h1` reports success with exit code 0 after an install.
- [x] 3.2 Make `verify` print a diagnostic naming the missing path and exit non-zero when either file is absent. Verify `make verify HERMES_HOME=/tmp/empty` exits non-zero with a message naming `plugin.yaml`.

## 4. Cross-platform and integration checks

- [x] 4.1 Confirm only portable utilities are used (`sh`, `mkdir`, `rm`, `cp`, `test`) and no GNU-only flags such as `cp --parents` or `rm -v` are present. Verify `grep -nE -- '--parents|-v[^a-z]' Makefile` returns no matches.
- [x] 4.2 Run the full lifecycle on macOS: `make install verify reinstall uninstall HERMES_HOME=/tmp/hermes-mac` and verify each step exits zero and the intermediate states match the spec scenarios.
- [x] 4.3 Run the same lifecycle on Linux (native or a container, e.g. `docker run --rm -v "$PWD":/w -w /w alpine sh -c 'apk add --no-cache make && make install verify reinstall uninstall HERMES_HOME=/tmp/hermes-linux'`) and verify it exits zero with the same intermediate states.
- [x] 4.4 Confirm `make help` lists `install`, `uninstall`, `reinstall`, and `verify`. Verify by inspecting the `make help` output.

## 5. Verify activation

- [x] 5.1 Extend `verify` to read `$(HERMES_HOME)/config.yaml` and exit non-zero with a diagnostic naming `plugins.enabled` when `openbao` is missing, and naming `secrets.openbao.enabled` when it is not `true`; warn and pass when the file is absent. Verify with four temp homes: plugin enabled plus source enabled (exit 0), plugin not enabled (names `plugins.enabled`), source disabled (names `secrets.openbao.enabled`), and no config (warning, exit 0).
- [x] 5.2 Update the `verify` line in the `help` target and the README "Verify the installation" section to describe the activation check, and confirm each documented command matches actual `make verify` behavior.
