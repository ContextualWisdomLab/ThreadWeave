# ThreadWeave Documentation Fitness Audit

**Assessment date:** 2026-08-10  
**Protected-main integration reference assessed:** `fe9b46f5404f368b311de205c4e647f47db89ab3`  
**Canonical documentation integration:** PR #25

## Verdict

The canonical product/technical/architecture graph is **DESIGN-SUFFICIENT** and **PROTECTED-MAIN-DOCUMENTATION-SUFFICIENT** at the assessed protected-main integration reference. A reviewer can reconstruct the supported product boundary, as-built runtime architecture, host responsibilities, public API/version contract, UML/state/deployment views, conceptual ERD, standards basis, security/privacy model, test/coverage policy, operability/recovery, incident/RCA process, release/provenance authority, ADR decisions, and requirements-to-evidence traceability from the repository without depending on this conversation.

This is deliberately **RELEASE-INSUFFICIENT**. Documentation integration is not PyPI publication, and Draft PR #20 remains an active-PR capability rather than protected-main behavior. Release blocker #17 still requires GitHub/PyPI Trusted Publisher account-side identity setup and verified public `0.2.0` artifacts.

## Protected-main evidence

PR #25 exact contributor head `f9c1b504802fd402e7dd4180d68ddfaf105dd51d` passed CI, SAST Semgrep, Security Scan, Python 3.10–3.14 lanes, package build/hash-install/outside-source smoke, workflow lint/lock integrity, and the canonical documentation contracts before integration.

Protected-main merge `fe9b46f5404f368b311de205c4e647f47db89ab3` then ran push CI as run `31354471651`. That protected-main run completed successfully, including lock/workflow validation, package build/hash-install/outside-source smoke, Python 3.10, 3.11, 3.12, 3.13, and 3.14 jobs, the focused autonomous/release boundary coverage gate, the full pytest coverage run, and `coverage report`. This is the evidence used below for protected-main documentation and coverage maturity. Future main changes must reacquire evidence rather than inherit this run.

## Artifact fitness matrix

| Documentation family | Protected-main state | Implementation truth |
|---|---|---|
| Documentation index | PRESENT-CURRENT | canonical discoverability map |
| PRD | PRESENT-CURRENT | protected-main + active-PR distinctions |
| TRD | PRESENT-CURRENT | protected-main + active-PR distinctions |
| root Architecture | PRESENT-CURRENT | protected-main as-built spine and host boundary |
| ADR index and detailed ADRs | PRESENT-CURRENT | Accepted/Proposed status is explicit |
| UML/component/sequence/state/deployment/authority views | PRESENT-CURRENT | active PR #20 target views are labelled non-main |
| ERD/domain model | PRESENT-CURRENT | conceptual; ThreadWeave owns no database |
| public API/version contract | PRESENT-CURRENT | in-process Python API, no invented HTTP contract |
| Security | PRESENT-CURRENT | runtime and automation trust boundaries |
| Threat Model | PRESENT-CURRENT | runtime/repository/supply-chain threats |
| Data Governance | PRESENT-CURRENT | host-owned PII purpose, retention, authorization and erasure boundary |
| Test Strategy | PRESENT-CURRENT | exact coverage, Python 3.10–3.14, realistic protocol/adversarial tests |
| Operability | PRESENT-CURRENT | library/host/release operation and recovery |
| Incident Runbook | PRESENT-CURRENT | owning-layer RCA and evidence identity |
| Release/Provenance/Licensing | PRESENT-CURRENT | Trusted Publishing, provenance, SBOM, Apache-2.0 boundary |
| Requirements/standards/evidence Traceability | PRESENT-CURRENT | main vs active-PR evidence separated |
| APA 7 doctoring/research | PRESENT-CURRENT | RFC/research sources and product decisions |
| AGENTS / CLAUDE / README / CHANGELOG | PRESENT-CURRENT | README is the customer/operator guide; hourly automation playbook lives in `docs/operations/` |

## Capability maturity vocabulary

- **IMPLEMENTED-ON-PROTECTED-MAIN** — integrated source/documented contract with representative protected-main evidence.
- **IMPLEMENTED-ON-ACTIVE-PR** — implementation exists only on an open PR.
- **PARTIAL** — only part of the accepted contract/evidence exists.
- **ACCEPTED-ARCHITECTURE** — decision governs architecture but implementation may be absent.
- **PLANNED** — accepted backlog without implementation evidence.
- **RESEARCH-ONLY** — exploratory evidence, not a product claim.
- **SUPERSEDED** — explicitly replaced by a later decision.
- **HOST-OWNED** — responsibility belongs to naruon/IMAP/archive wrapper rather than this package.
- **OUT-OF-SCOPE** — intentionally excluded from ThreadWeave ownership.

## Current capability assessment

| Capability | Maturity | Evidence/notes |
|---|---|---|
| canonical reference threading | IMPLEMENTED-ON-PROTECTED-MAIN | `threading`, `container`, RFC regression suite |
| RFC 5256 subject grouping | IMPLEMENTED-ON-PROTECTED-MAIN | `subject`, `collation`, grouping tests |
| sent-date ordering | IMPLEMENTED-ON-PROTECTED-MAIN | `dates`, `threading`, ordering tests |
| THREAD / UID THREAD serialization | IMPLEMENTED-ON-PROTECTED-MAIN | `imap`, protocol tests |
| adapter input-order/public-sequence authority separation | IMPLEMENTED-ON-PROTECTED-MAIN | protected-main PR #26 merge `8af58f1`; explicit host identifiers still serialize while iterable order stays internal |
| work-conserving hourly OpenCode task prompt | IMPLEMENTED-ON-PROTECTED-MAIN | protected-main PR #28 merge `ab4595f`; one bounded proposal with two internal exit sweeps |
| Python 3.10–3.14 CI/package compatibility | IMPLEMENTED-ON-PROTECTED-MAIN | PR #27 merge `4fa4caf`; re-proven by protected-main push CI run `31354471651` after docs integration |
| canonical documentation reconstruction graph | IMPLEMENTED-ON-PROTECTED-MAIN | protected-main PR #25 merge `fe9b46f`; this audit plus machine-checkable documentation contracts |
| 100% production statement/branch coverage | IMPLEMENTED-ON-PROTECTED-MAIN | protected-main push CI run `31354471651` completed the focused coverage gate, full coverage test run, and coverage report successfully; must be re-proven for every later merge/release head |
| incremental mailbox state / RFC 8474 handoff | IMPLEMENTED-ON-ACTIVE-PR | Draft PR #20; not a protected-main claim |
| payload-free incremental snapshot schema | IMPLEMENTED-ON-ACTIVE-PR | Draft PR #20 |
| first PyPI 0.2.0 trusted publication | PARTIAL | repository release machinery is present; account/environment/public-artifact acceptance remains open in issue #17 |
| distributed mailbox persistence / auth / tenancy | HOST-OWNED | naruon or another host owns durable service state and access control |
| physical ThreadWeave database schema | OUT-OF-SCOPE | conceptual ERD is intentional; no database driver exists |

## Durable whole-conversation decisions

The protected repository graph now preserves these durable decisions rather than relying on chat history:

1. review → root-cause repair → exact-head revalidation → merge → next work is a work-conserving loop;
2. queued reviewer/check/provider latency blocks only the affected lane;
3. contributor head, PR-base snapshot, independently resolved live protected-base tip, and tested/synthetic checkout identity are different evidence identities;
4. the development model never owns independent review, merge, tag, or release authority;
5. scheduled model-backed development uses OpenCode with `NVIDIA_NIM_API_KEY`; `COPILOT_GITHUB_TOKEN` is not a development-model credential;
6. self-modifying/one-shot/encoded-patch branch-repair workflows are not an accepted maintenance mechanism;
7. ThreadWeave remains independently usable and integrates with naruon/other hosts only through typed public boundaries;
8. active PR behavior is never documented as shipped/protected-main behavior;
9. useful PII-bearing email metadata is governed by host purpose, authorization, selective logging, encryption/retention and audit rather than blanket masking that destroys function;
10. release claims require exact protected-head CI/security/coverage/package/provenance/review evidence plus post-publication artifact verification;
11. supported Python versions follow exact protected-main matrix/package evidence rather than `requires-python` syntax alone.

## Remaining executable gaps

Documentation sufficiency is not completion. Current remaining lanes are:

- issue #17: configure the GitHub `pypi` environment and the PyPI Trusted Publisher identity, dispatch `0.2.0` only from a then-current protected head, and verify public wheel/sdist/provenance plus a clean install; the public PyPI project still exposes 0.1.0 only at the latest audit probe;
- issue #22: after the open PR queue is genuinely drained and release policy permits, execute the final protected-main OpenCode/NVIDIA operational-acceptance path; criteria 1–4 are already satisfied;
- Draft PR #20: only after the `0.2.0` publication boundary closes, refresh it onto released protected main, resolve conflicts, rerun Python 3.10–3.14 exact-head gates plus mailbox-scale parity/performance evidence, obtain current-head independent review, and merge only if policy permits;
- after every integration or release, re-audit the graph and immediately continue to the next host-visible interoperability, resource-efficiency, operability, or ecosystem gap.

## Acceptance rule

Protected-main documentation sufficiency is green when all canonical documents exist and are linked, architecture/ADR/maturity claims agree with protected source and public API, active-PR behavior is explicitly non-main, conceptual ERD ownership is truthful, requirements are traceable to standards/code/tests/evidence, governance/release trust boundaries are normative and machine-checked, and exact protected-main verification exists for the assessed integration identity. Release readiness remains a separate gate.