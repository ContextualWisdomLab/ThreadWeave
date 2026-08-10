# ThreadWeave Documentation Fitness Audit

**Assessment date:** 2026-08-10  
**Protected-main reference assessed:** `ab4595f19bd94c83e15c934f96c4d05f90fbccf5`  
**Canonical documentation line:** PR #25 / `docs/product-architecture-baseline-2026-08-09` (mutable contributor head; refetch the exact head from GitHub before any merge/release decision)

The protected-main reference above is the fixed as-built baseline assessed by this audit. PR #25's contributor head is intentionally not frozen in this timeless document: it changes on every documentation correction. ADR-0007 requires the live contributor head, PR base snapshot, live protected-base tip, and tested checkout identity to be captured separately in current GitHub evidence.

## Verdict

The documentation line is **DESIGN-SUFFICIENT once this PR's documentation contracts pass**, but the repository remains **PROTECTED-MAIN-INSUFFICIENT** until the canonical graph is merged and proven on protected `main`.

The earlier PRD/TRD/Architecture/UML/ERD pack was materially strong but incomplete for acquisition-grade reconstruction because it did not yet contain a dedicated documentation fitness record, data-governance/privacy boundary, incident runbook, release/provenance/licensing authority, or explicit autonomous-maintenance/evidence-identity ADRs. Those omissions are tracked and repaired on this canonical branch rather than in a parallel documentation PR.

## Artifact fitness matrix

| Documentation family | State on this canonical line | Implementation truth |
|---|---|---|
| PRD | PRESENT-CURRENT | protected-main + active-PR distinctions |
| TRD | PRESENT-CURRENT | protected-main + active-PR distinctions |
| root Architecture | PRESENT-CURRENT | protected-main as-built spine |
| ADR index and detailed ADRs | PRESENT-CURRENT after ADR-0006/0007 | accepted/proposed status is explicit |
| UML/component/sequence/state/deployment views | PRESENT-CURRENT | active PR #20 views labelled target-only |
| ERD/domain model | PRESENT-CURRENT | conceptual; ThreadWeave owns no DB |
| public API/version contract | PRESENT-CURRENT after sequence-authority reconciliation | in-process Python API, no invented HTTP contract |
| Security | PRESENT-CURRENT | runtime and automation boundaries |
| Threat Model | PRESENT-CURRENT | repository/runtime threats |
| Test Strategy | PRESENT-CURRENT | exact coverage and realistic protocol tests |
| Operability | PRESENT-CURRENT | library/host/release operation |
| Incident Runbook | PRESENT-CURRENT after sequence-authority reconciliation | RCA and recovery authority |
| Data governance/privacy/retention | PRESENT-CURRENT | host-owned PII purpose/retention authority |
| Release/provenance/licensing | PRESENT-CURRENT | package/release evidence and Apache-2.0 boundary |
| Requirements/standards/evidence traceability | PRESENT-CURRENT after reconciliation | main vs active-PR evidence separated |
| Standards/APA 7 doctoring | PRESENT-CURRENT for protocol/research scope | authoritative RFC/research sources |
| AGENTS / CLAUDE / README / CHANGELOG | PRESENT-CURRENT after branch reconciliation | repository operating context |

## Capability maturity matrix

Use only these meanings in architecture decisions and audits:

- **IMPLEMENTED-ON-PROTECTED-MAIN** — source is integrated on protected `main` and representative repository evidence exists.
- **IMPLEMENTED-ON-ACTIVE-PR** — implementation exists only on an open PR.
- **PARTIAL** — only part of the accepted contract exists.
- **ACCEPTED-ARCHITECTURE** — decision is accepted but implementation may be absent.
- **PLANNED** — accepted backlog without implementation.
- **RESEARCH-ONLY** — exploratory evidence, not a product claim.
- **SUPERSEDED** — explicitly replaced by a later decision.
- **OUT-OF-SCOPE** — intentionally outside ThreadWeave ownership.

For legacy documents that already use `implemented-main` or `active-PR`, those labels map respectively to IMPLEMENTED-ON-PROTECTED-MAIN and IMPLEMENTED-ON-ACTIVE-PR. New documentation should prefer the explicit long form when ambiguity matters.

## Current capability assessment

| Capability | Maturity | Evidence/notes |
|---|---|---|
| canonical reference threading | IMPLEMENTED-ON-PROTECTED-MAIN | `threading`, `container`, RFC regression suite |
| RFC 5256 subject grouping | IMPLEMENTED-ON-PROTECTED-MAIN | `subject`, `collation`, grouping tests |
| sent-date ordering | IMPLEMENTED-ON-PROTECTED-MAIN | `dates`, `threading`, ordering tests |
| THREAD / UID THREAD serialization | IMPLEMENTED-ON-PROTECTED-MAIN | `imap`, protocol tests |
| adapter input-order/public-sequence authority separation | IMPLEMENTED-ON-PROTECTED-MAIN | protected-main PR #26 merge `8af58f1`: bulk adapter leaves public sequence/UID metadata unset; explicit host identifiers still serialize |
| work-conserving hourly OpenCode task prompt | IMPLEMENTED-ON-PROTECTED-MAIN | protected-main PR #28 merge `ab4595f`: one bounded proposal remains the authority boundary while the agent must continue safe sub-steps and complete two internal exit sweeps |
| incremental mailbox state / RFC 8474 handoff | IMPLEMENTED-ON-ACTIVE-PR | Draft PR #20; not a protected-main claim |
| payload-free incremental snapshot schema | IMPLEMENTED-ON-ACTIVE-PR | Draft PR #20 |
| 100% production statement/branch coverage | PARTIAL | required CI contract exists on protected main, but this audit does not embed a same-SHA protected-main coverage run; exact coverage must be re-proven and linked for each merge/release head |
| Python 3.14 CI/package compatibility | IMPLEMENTED-ON-ACTIVE-PR | PR #27 proves 3.10–3.14 test lanes and Python 3.14 package build/hash-install/outside-source smoke; not protected-main until merge |
| first PyPI 0.2.0 trusted publication | PARTIAL / EXTERNAL-BOUNDARY GAP | repository release machinery exists; account/environment publication evidence is separately required |
| physical database schema | OUT-OF-SCOPE | host-owned; conceptual ERD is intentional |

## Whole-conversation decisions that must remain durable

The canonical repository graph must preserve these durable product/governance decisions rather than relying on chat history:

1. review → root-cause repair → exact-head revalidation → merge → next work is a continuous work-conserving loop;
2. queued CI/reviewer latency is item-local and never a reason to stop other safe work;
3. exact contributor head, PR base snapshot, and independently resolved live base tip are different evidence identities;
4. the development model never owns independent review, merge, tag, or release authority;
5. scheduled model-backed development uses OpenCode with `NVIDIA_NIM_API_KEY`; `COPILOT_GITHUB_TOKEN` is not a development-model credential;
6. one-shot/self-modifying/encoded-patch branch repair workflows are not an accepted repository maintenance mechanism;
7. ThreadWeave remains independently usable while supporting typed integration with naruon and other hosts;
8. active PR behavior is never documented as shipped/protected-main behavior;
9. PII-bearing email metadata must be protected by purpose-bound host authorization, selective logging, encryption/retention controls, and audit rather than blanket masking that destroys product utility;
10. release claims require exact protected-head CI/security/coverage/package/provenance/review evidence plus post-publication artifact verification.

## Remaining executable gaps

This audit is not completion. The current queue still includes:

- repair and re-run PR #25 after any exact-head CI/review finding;
- integrate the documentation graph only when all required gates pass;
- land PR #27 only after exact-head 3.10–3.14/security/review gates pass, then move Python 3.14 maturity to IMPLEMENTED-ON-PROTECTED-MAIN;
- verify protected-main scheduled/manual product-development execution after PR #28 using the unchanged one-proposal/NVIDIA credential/reverification/publisher boundaries; issue #22 retains that operational-acceptance tail;
- resolve the `0.2.0` trusted-publishing external identity/environment acceptance path;
- only after that release boundary closes, refresh PR #20 onto current protected `main`, rerun mailbox-scale parity/performance evidence, obtain current-head review, and merge if policy permits;
- after every integration, re-audit the graph and immediately continue to the next buyer-visible or release-readiness gap.

## Acceptance rule

A documentation audit is green only when all canonical files exist, the index links them, ADR status and active-PR maturity are machine-checked, the graph agrees with current source/workflows/public API, known contract mismatches have executable owners, and no active-PR or conversation-only proposal is promoted to protected-main truth. A green documentation PR is still an intermediate event until protected-main integration and the broader repository queue are re-evaluated.