# Design

## Context

See `proposal.md` - Why. This is a documentation-only change that rewrites `README.md`; it does not touch code. The constraints that shape the approach:

- The plugin is small and single-purpose, and the repository already uses `README.md` as its only documentation entry point.
- The behavioral contract the README must describe (`secrets.openbao.*` keys, `OPENBAO_*`/`VAULT_*` environment variables, the `openbao://<mount>/<path>#<key>` grammar, protected token variables, and the `ErrorKind` set) is already specified in the `add-openbao-secret-source` spec delta and implemented under `src/hermes_openbao_secret_source/`. The README documents that contract; it must not invent a new one.
- The `add-openbao-secret-source` change is still in progress and includes its own README tasks, so the two changes overlap on the same file.
- Project context requires artifacts in English.

## Goals / Non-Goals

**Goals:**
- A single `README.md` that takes an operator from "no plugin installed" to "credentials resolving from OpenBao" through task-ordered instructions.
- Documentation that is a faithful mirror of the plugin's actual configuration surface and reference grammar, with every documented key traceable to the spec or code.
- A troubleshooting path keyed by the machine-readable `ErrorKind` values the source already emits.

**Non-Goals:**
- No separate documentation site, `docs/` tree, or generated API reference.
- No changes to code, configuration keys, reference grammar, `plugin.yaml`, or packaging.
- No new behavioral specification; documentation does not become a second source of truth for behavior.
- No localization; the README stays English.

## Decisions

### D1: One `README.md`, no `docs/` tree
Keep all usage documentation in the repository root `README.md`.

- Rationale: the plugin is a single small package; a reviewable file at the repo root is the fastest path for an operator and avoids documentation sprawl for a change of this size. The user explicitly chose this form.
- Alternatives: a `docs/` directory with per-topic pages (better only if the surface grows substantially); a docs site generator (unjustified for one small plugin).
- Consequence: the README will be longer; use a table of contents and clear headings so it stays navigable.

### D2: Task-ordered structure with reference after the quickstart
Order the document so the happy path comes first, and the complete reference follows:

1. Overview / what it does
2. Prerequisites
3. Installation (package install and `~/.hermes/plugins/openbao/` placement)
4. Enable the source
5. Quickstart: minimal working `secrets.openbao` example
6. Reference grammar (`openbao://<mount>/<path>#<key>`)
7. Configuration reference (keys, types, defaults) and environment variables
8. Behavior notes (fail-open, partial tolerance, protected token, timeout, precedence/provenance)
9. Troubleshooting by `ErrorKind`
10. Security notes

- Rationale: an operator can stop after the quickstart; a reference-first layout would bury the shortest path to a working setup.
- Alternative: reference-first (better for returning users; can be reached via the table of contents).

### D3: The spec/implementation is the source of truth; the README mirrors it
Document only keys, defaults, ref forms, and error kinds that exist in the `add-openbao-secret-source` spec delta or the implementation. Do not introduce aspirational keys or undocumented behavior.

- Rationale: prevents documentation drift and false promises; keeps the README checkable against the spec.
- Alternative: document intended-future features (rejected; mixes shipped and unshipped behavior).

### D4: Prefer a verifiable configuration example
The primary worked example should reuse values that also appear in the plugin's tests or spec scenarios (for example `OPENAI_API_KEY` mapped to `openbao://secret/team/llm#api_key`), so the documented example is already exercised.

- Rationale: a README example that is also a test fixture cannot silently rot into a form the parser rejects.
- Alternative: freely invented examples (higher risk of a documented ref that no test covers).

### D5: Reconcile with the in-flight `add-openbao-secret-source` change
This change owns the user-facing usage documentation. The README is written once; whichever change lands second updates the README as needed rather than re-authoring it.

- Rationale: both changes currently target README tasks (3.5 and 5.3 in the other change); authoring it twice would create conflicting text.
- Alternative: fold documentation into the other change (rejected because the user explicitly requested a dedicated change).

## Risks / Trade-offs

- [Documentation drifts from the implementation while `add-openbao-secret-source` is still in progress] → Ground every key, default, and ref form in the spec delta or code, and add a task that re-verifies the README against the implementation before this change is archived.
- [Overlap with the other change's README tasks causes merge conflict or duplicated effort] → D5 assigns ownership; note the overlap in the proposal and reconcile when the second change lands.
- [A README that grows too large becomes hard to scan] → D2's task-ordered layout plus a table of contents; keep prose tight and prefer tables for key/default reference.
- [Examples that reference specific providers age poorly] → Keep the worked example generic where possible and treat provider-specific mappings as illustrative, not prescriptive.

## Migration Plan

- Documentation-only: no runtime, data, or configuration migration.
- Rollout: update `README.md` on the branch for this change; no release artifact behavior changes.
- Rollback: revert the `README.md` commit; the stub README returns with no functional impact.

## Open Questions

- None. The documentation form (README-only) and language (English) were settled with the user, and the remaining content is fully determined by the existing spec delta and implementation.
