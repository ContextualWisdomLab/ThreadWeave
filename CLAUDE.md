# ThreadWeave Agent Context

ThreadWeave is a deterministic, standards-grounded email-threading library. Repository code and the canonical documentation graph are authoritative; chat history, PR bodies, and generated summaries are supporting evidence only.

## Read first

Before changing product behavior or architecture, read:

- `AGENTS.md`
- `DOCUMENTATION.md`
- `docs/PRD.md`
- `docs/TRD.md`
- `ARCHITECTURE.md`
- `docs/adr/README.md`
- `docs/TRACEABILITY.md`
- `docs/TEST_STRATEGY.md`
- `docs/SECURITY.md`

## Product boundaries

- Preserve `thread_messages` as the canonical structural correctness oracle unless an Accepted ADR explicitly supersedes that decision.
- Keep the package usable as a zero-runtime-dependency standalone library and as a typed module inside naruon or another host.
- Hosts own authentication, tenancy, mailbox persistence/synchronization, distributed locking, remote API lifecycle, durable audit, and deployment controls.
- Do not invent a ThreadWeave database merely to satisfy an ERD. The current ERD is conceptual because the library owns no persistence.
- Active PR behavior is not protected-main behavior. In particular, incremental mailbox state and RFC 8474 identity/snapshot contracts remain active-PR architecture until integrated.

## Development rules

- Use test-driven development for behavior changes: establish a realistic failing regression, implement the narrowest root-cause fix, then run focused and full verification.
- Maintain exact 100% owned production statement and branch coverage and beginner-readable public docstrings.
- Keep Python runtime/CI support claims synchronized with package metadata and the complete test matrix; Python 3.14 coverage is an explicit current gap until implemented and proven.
- Use exact current-head and independently resolved live-base evidence for merge decisions. Queued, skipped, stale, cancelled, synthetic-only, status-only, or predecessor-head evidence is not passing.
- Never weaken required checks, manufacture approval, or use a no-op source change merely to retrigger an external reviewer.
- Never add self-modifying, one-shot branch-repair, or encoded-patch workflows as a substitute for a normal auditable source change.

## Automation and credentials

- Scheduled autonomous development uses an immutably pinned OpenCode Agent and `NVIDIA_NIM_API_KEY` only for actual model-backed execution.
- `COPILOT_GITHUB_TOKEN` is not a development-model credential and must not be introduced into the autonomous development path.
- Keep development-model credentials separate from deterministic verification, PR publication, independent review, merge, and release authority.
- Central organization workflows and repositories with their own active writer loops are dependencies, not implicit write targets.

## Documentation and release

Material changes to runtime capability, persistence, identity, Unicode/collation, ordering defaults, protocol authority, durable state, automation authority, or release evidence require the affected PRD/TRD/Architecture/ADR/UML/ERD/security/test/operability/traceability records to be reconciled in the same workstream.

Release only from one exact integrated protected head that satisfies applicable CI, security, coverage/docstring, packaging, provenance/SBOM, compatibility, review, and release-acceptance gates. Update `CHANGELOG.md` and version metadata together and verify the published artifact after release.