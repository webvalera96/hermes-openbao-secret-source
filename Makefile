# Makefile for installing the OpenBao secret source plugin into a local Hermes agent.
#
# Usage:
#   make                 # show help
#   make install         # install into $(HERMES_HOME)/plugins/openbao
#   make uninstall       # remove the installed plugin
#   make reinstall       # uninstall then install
#   make verify          # check the install and, when configured, that openbao is active
#
# Override the Hermes home on the command line or via the environment:
#   make install HERMES_HOME=/opt/hermes

HERMES_HOME ?= $(HOME)/.hermes
PLUGIN_DIR  := $(HERMES_HOME)/plugins/openbao
CONFIG_FILE := $(HERMES_HOME)/config.yaml
SCRIPT_SRC  := src/hermes_openbao_secret_source

.DEFAULT_GOAL := help

.PHONY: install uninstall reinstall verify help

help: ## Show the available targets
	@echo "OpenBao secret source plugin installer"
	@echo ""
	@echo "Usage: make <target> [HERMES_HOME=/path]"
	@echo ""
	@echo "Targets:"
	@echo "  install    Copy the plugin package into $(PLUGIN_DIR)"
	@echo "  uninstall  Remove $(PLUGIN_DIR)"
	@echo "  reinstall  Uninstall then install"
	@echo "  verify     Check the install and, when configured, that openbao is active"
	@echo "  help       Show this help"

install: ## Copy the plugin package into the Hermes home
	@mkdir -p "$(dir $(PLUGIN_DIR))"
	@rm -rf "$(PLUGIN_DIR)"
	@cp -R "$(SCRIPT_SRC)" "$(PLUGIN_DIR)"
	@echo "Installed plugin to $(PLUGIN_DIR)"

uninstall: ## Remove the installed plugin
	@rm -rf "$(PLUGIN_DIR)"
	@echo "Removed $(PLUGIN_DIR)"

reinstall: uninstall install ## Uninstall then install
	@:

verify: ## Check the install and, when configured, that openbao is active
	@if [ ! -f "$(PLUGIN_DIR)/plugin.yaml" ]; then \
		echo "verify failed: missing $(PLUGIN_DIR)/plugin.yaml" >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(PLUGIN_DIR)/__init__.py" ]; then \
		echo "verify failed: missing $(PLUGIN_DIR)/__init__.py" >&2; \
		exit 1; \
	fi
	@if [ ! -f "$(CONFIG_FILE)" ]; then \
		echo "verify: $(PLUGIN_DIR) installed, but no $(CONFIG_FILE) yet; enable the plugin and set secrets.openbao.enabled: true to activate" >&2; \
	else \
		if ! awk '/^[[:space:]]*#/ { next } /^plugins:[[:space:]]*$$/ { in_p=1; next } /^[^[:space:]]/ { in_p=0 } in_p && /^[[:space:]]+enabled:[[:space:]]*$$/ { want=1; next } in_p && /^[[:space:]]+enabled:.*openbao/ { found=1; next } in_p && want && /^[[:space:]]+-[[:space:]]*"?openbao"?[[:space:]]*$$/ { found=1; next } in_p && /^  [A-Za-z_]/ { want=0 } END { exit found ? 0 : 1 }' "$(CONFIG_FILE)"; then \
			echo "verify failed: 'openbao' is not listed under plugins.enabled in $(CONFIG_FILE) (run: hermes plugins enable openbao)" >&2; \
			exit 1; \
		fi; \
		if ! awk '/^[[:space:]]*#/ { next } /^secrets:[[:space:]]*$$/ { in_s=1; next } /^[^[:space:]]/ { in_s=0 } in_s && /^[[:space:]]+openbao:[[:space:]]*$$/ { in_o=1; next } in_s && in_o && /^[[:space:]]+enabled:[[:space:]]*true[[:space:]]*$$/ { found=1; next } in_s && /^  [A-Za-z_]/ { in_o=0 } END { exit found ? 0 : 1 }' "$(CONFIG_FILE)"; then \
			echo "verify failed: secrets.openbao.enabled is not true in $(CONFIG_FILE) (set secrets.openbao.enabled: true)" >&2; \
			exit 1; \
		fi; \
		echo "verify: $(PLUGIN_DIR) installed and openbao source enabled"; \
	fi
