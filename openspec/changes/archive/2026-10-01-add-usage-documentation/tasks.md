# Tasks

## 1. Ground the documentation in the actual contract

- [x] 1.1 Inventory the documented surface by reading `openspec/changes/add-openbao-secret-source/specs/openbao-secret-source/spec.md` and `src/hermes_openbao_secret_source/config.py`, and list every `secrets.openbao.*` key, default constant, environment variable, ref-grammar rule, and `ErrorKind` value; verify the inventory is complete by running `grep -nE "DEFAULT_|_ENV|ErrorKind|def resolve_" src/hermes_openbao_secret_source/config.py` and confirming each occurrence is represented
- [x] 1.2 Select the primary worked example ref and confirm it is valid for the documented grammar; verify with `uv run python -c "print('openbao://secret/team/llm#api_key')"` plus a check that the same ref appears in the spec delta or tests, so the README example cannot drift from the parser

## 2. Author README core usage sections

- [x] 2.1 Write the overview, prerequisites, installation, enablement, and quickstart sections in `README.md`, including the `~/.hermes/plugins/openbao/` placement and the `secrets.openbao.enabled: true` switch; verify the quickstart uses only keys from the task 1.1 inventory and that every relative link in these sections resolves
- [x] 2.2 Write the reference-grammar section (`openbao://<mount>/<path>#<key>`, mount defaulting, rejected/ambiguous forms) and the configuration reference tables for every key (type, default, description) and every environment variable; verify each documented key matches the constants in `src/hermes_openbao_secret_source/config.py` and the spec delta

## 3. Author README behavior and troubleshooting sections

- [x] 3.1 Write the behavior notes covering fail-open `fetch()`, per-entry partial tolerance, protected token variables, the timeout budget, and orchestrator-owned precedence/provenance; verify each statement maps to a requirement or scenario in the `add-openbao-secret-source` spec delta
- [x] 3.2 Write the troubleshooting section as an `ErrorKind` -> symptoms -> fix table covering `NOT_CONFIGURED`, `BINARY_MISSING`, `AUTH_FAILED`, `AUTH_EXPIRED`, `REF_INVALID`, `NETWORK`, `EMPTY_VALUE`, `TIMEOUT`, and `INTERNAL`; verify no emitted error kind is missing from the table
- [x] 3.3 Write the security notes (static-token trust model, why token variables are protected) and add a table of contents; verify the table of contents links match the actual README headings

## 4. Validate and reconcile

- [x] 4.1 Verify the documented configuration example is valid by extracting it to a temp file and parsing it with `uv run python -c "import yaml,pathlib;print(yaml.safe_load(pathlib.Path('<example>').read_text()))"`, and confirm any README example already covered by a test still passes with `uv run pytest`
- [x] 4.2 Reconcile the README against the in-flight `add-openbao-secret-source` change: mark this change as owning the usage documentation and ensure README tasks 3.5 and 5.3 in that change are treated as superseded; verify no contradictory README instructions remain between the two changes
- [x] 4.3 Run `openspec validate add-usage-documentation --strict` and verify the change validates with no errors
