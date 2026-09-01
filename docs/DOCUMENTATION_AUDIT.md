# ThreadWeave Documentation Fitness Audit

**Assessment date:** 2026-09-01  
**Protected-main historical evidence reference:** PR #25 merge `fe9b46f5404f368b311de205c4e647f47db89ab3`  
**Active release-authority candidate:** PR #35

## Verdict

The canonical product/technical/architecture graph remains **DESIGN-SUFFICIENT** and **PROTECTED-MAIN-DOCUMENTATION-SUFFICIENT** for the implemented library boundary. A reviewer can reconstruct the supported product, host responsibilities, public API/version contract, architecture/ERD, standards basis, security/privacy model, test policy, operability/recovery, incident/RCA process, release authority, ADR decisions, and evidence traceability without relying on conversation history.

The repository is still **RELEASE-INSUFFICIENT** until public `threadweave==0.2.0` evidence exists. The reason is no longer an external Trusted Publisher prerequisite. PR #35 implements the accepted organization `PIPY_TOKEN` publisher path and public digest/install verification, but those changes are active-PR behavior until integrated and the resulting protected-main release run succeeds. **Draft PR #20** remains **IMPLEMENTED-ON-ACTIVE-PR**, not protected-main/released functionality.

## Protected-main historical evidence

PR #25 exact contributor head passed CI, SAST Semgrep, Security Scan, Python 3.10–3.14 lanes, package build/hash-install/outside-source smoke, workflow lint/lock integrity, and canonical documentation contracts before integration.

Protected-main push CI run `31354471651` then completed successfully after PR #25 integration, including lock/workflow validation, package build/hash-install/outside-source smoke, Python 3.10, 3.11, 3.12, 3.13, and 3.14 jobs, focused automation/release-boundary coverage, full pytest coverage, and coverage reporting. This remains historical evidence only; PR #35 must acquire its own exact-head evidence before merge/release.

## Artifact fitness matrix

| Documentation family | State | Current truth |
|---|---|---|
| Documentation index | PRESENT-CURRENT | canonical discoverability map |
| PRD / TRD / Architecture | PRESENT-CURRENT | protected-main product vs active release/incremental PR distinctions |
| ADR index and detailed ADRs | PRESENT-CURRENT | ADR-0008 amended for approved publisher identity; Accepted/Proposed status explicit |
| UML / ERD / API contract | PRESENT-CURRENT | conceptual/threading boundary; no invented persistence or HTTP contract |
| Security / Threat Model / Data Governance | PRESENT-CURRENT | runtime, automation, host-owned PII and credential boundaries |
| Test Strategy | PRESENT-CURRENT | exact coverage, Python 3.10–3.14, realistic protocol/adversarial tests |
| Operability / Incident Runbook | PRESENT-CURRENT | owning-layer RCA, publisher recovery and exact evidence identity |
| Release/Provenance/Licensing | PRESENT-CURRENT | approved secret-backed publisher, optional Trusted Publishing, SLSA/SPDX, Apache-2.0, public digest/install completion boundary |
| Traceability / product gap baseline | PRESENT-CURRENT | main vs active-PR/release evidence and cross-repository ownership separated |
| APA 7 doctoring/research | PRESENT-CURRENT | protocol/research sources plus release authority references |
| AGENTS / CLAUDE / README / CHANGELOG | PRESENT-CURRENT | customer/operator README, current 0.2.0 release notes, automation playbook under `docs/operations/` |

## Capability maturity vocabulary

- **IMPLEMENTED-ON-PROTECTED-MAIN** — integrated source/documented contract with representative protected-main evidence.
- **IMPLEMENTED-ON-ACTIVE-PR** — implementation exists only on an open PR.
- **PARTIAL** — only part of the accepted contract/evidence exists.
- **ACCEPTED-ARCHITECTURE** — decision governs architecture but implementation/public proof may be absent.
- **HOST-OWNED** — responsibility belongs to a host product rather than this package.
- **OUT-OF-SCOPE** — intentionally excluded from ThreadWeave ownership.

## Current capability assessment

| Capability | Maturity | Evidence/notes |
|---|---|---|
| canonical reference threading | IMPLEMENTED-ON-PROTECTED-MAIN | `threading`, `container`, RFC regression suite |
| RFC 5256 subject grouping | IMPLEMENTED-ON-PROTECTED-MAIN | `subject`, `collation`, grouping tests |
| sent-date ordering | IMPLEMENTED-ON-PROTECTED-MAIN | `dates`, `threading`, ordering tests |
| THREAD / UID THREAD serialization | IMPLEMENTED-ON-PROTECTED-MAIN | `imap`, protocol tests |
| adapter input-order/public-sequence authority separation | IMPLEMENTED-ON-PROTECTED-MAIN | protected-main PR #26; host IDs stay authoritative |
| work-conserving hourly OpenCode task prompt | IMPLEMENTED-ON-PROTECTED-MAIN | protected-main PR #28 |
| Python 3.10–3.14 CI/package compatibility | IMPLEMENTED-ON-PROTECTED-MAIN | PR #27 merge `4fa4caf`; re-proven by protected-main push CI run `31354471651` |
| canonical documentation reconstruction graph | IMPLEMENTED-ON-PROTECTED-MAIN | PR #25 merge `fe9b46f`; canonical documentation contracts |
| 100% production statement/branch coverage | IMPLEMENTED-ON-PROTECTED-MAIN | protected-main push CI run `31354471651`; must be re-proven for every later merge/release head |
| Actions registry lifecycle detector | IMPLEMENTED-ON-PROTECTED-MAIN | merged PR #32 / ADR-0010; read-only detector separate from operator mutation |
| incremental mailbox state / RFC 8474 handoff | IMPLEMENTED-ON-ACTIVE-PR | Draft PR #20; not a protected-main claim |
| payload-free incremental snapshot schema | IMPLEMENTED-ON-ACTIVE-PR | Draft PR #20 |
| approved PyPI API-token release authority | IMPLEMENTED-ON-ACTIVE-PR | PR #35; token isolated to pinned publisher, OIDC optional |
| changelog-driven protected-main auto-release | IMPLEMENTED-ON-ACTIVE-PR | PR #35; automatic watched-path trigger plus manual idempotent recovery |
| first public PyPI 0.2.0 release | PARTIAL | package/version/changelog candidate exists; exact protected-main release and public artifact proof still required |
| distributed mailbox persistence / auth / tenancy | HOST-OWNED | naruon or another host owns durable state/access control |
| physical ThreadWeave database schema | OUT-OF-SCOPE | conceptual ERD is intentional; no database driver exists |

## Durable release decisions

1. A merge is not a release and a GitHub Release alone is not public-package completion.
2. Generic fleet changelog/tag/GitHub Release governance belongs to `ContextualWisdomLab/.github#1552`; ThreadWeave retains its product-specific Python build/publisher adapter.
3. Release version and customer notes are derived from reviewed package metadata and `CHANGELOG.md`; material `Unreleased` notes must not be omitted from a final release.
4. The selected publisher is resolved before irreversible work. The current accepted mode is the organization secret `PIPY_TOKEN`; only its boolean availability may be observed before the isolated publisher job.
5. `PIPY_USERNAME` is deliberately not materialized for API-token publication because the pinned PyPA publisher uses the standard `__token__` username.
6. Trusted Publishing remains an optional future credential-minimization mode; it is not the current external release blocker.
7. Secret values never belong in build/test/model jobs, logs, artifacts, outputs, cache keys, SBOM/provenance, or release receipts.
8. Public release completion requires PyPI wheel/sdist filename and SHA-256 equality with the reviewed bundle plus a clean public install and representative `THREAD`/`UID THREAD` smoke.
9. Published PyPI versions/files and release tags are immutable; failure recovery verifies/retries exact evidence rather than rewriting it.

## Remaining executable gaps

- **PR #35 / issue #17:** finish current-head review and CI/SAST/Security gates, merge normally, observe the resulting protected-main automatic release, verify public 0.2.0 digests/install, then close #17.
- **Issue #31:** use merged PR #32 detector evidence for authorized cleanup of confirmed orphan Actions identities; do not grant mutation authority to the detector.
- **Issue #22:** execute the final bounded model-path operational proof only when truthful release/PR state permits.
- **Draft PR #20:** after verified 0.2.0 publication, refresh onto released protected main, resolve conflicts, reacquire Python 3.10–3.14/coverage/package/security/review and mailbox-scale parity evidence, then integrate only if policy permits.

## Acceptance rule

Protected-main documentation sufficiency is green when canonical documents exist and are linked, architecture/ADR/maturity claims agree with protected source and public API, active-PR behavior is explicitly non-main, conceptual ERD ownership is truthful, requirements are traceable to standards/code/tests/evidence, and exact protected-main verification exists for the assessed integration identity. Release readiness and public release completion remain separate gates.
