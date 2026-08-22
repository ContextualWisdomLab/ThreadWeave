# ThreadWeave Incident and RCA Runbook

**Status:** Accepted repository-operating guidance  
**Last reviewed:** 2026-08-10

ThreadWeave is a library, so incidents generally present as incorrect thread structure, malformed protocol output, resource exhaustion, package/release failure, or repository automation/security failure inside a consuming host or delivery pipeline.

## Incident principles

- Restore evidence before changing code: record exact package/commit, inputs or bounded reproducer, options, host metadata class, failing check/run/job, and the first observable incorrect boundary.
- Fix the owning layer rather than compensating downstream.
- Reproduce with a failing regression before a behavior fix when repository code is at fault.
- Never relax a correctness/security/coverage gate to make an incident disappear.
- A queued or externally unavailable reviewer/check is an item-local state; continue other safe repository work while periodically refetching it.

## First-response classification

| Symptom | First layer to inspect | Typical owner |
|---|---|---|
| wrong parent/forest shape | headers → canonical `threading`/`container` | ThreadWeave |
| wrong subject grouping | `subject` / `collation` | ThreadWeave |
| wrong order | `dates` → ordering stages | ThreadWeave or host metadata |
| malformed THREAD response | `imap` projection/identifier input | ThreadWeave or host metadata |
| duplicate/missing UID/sequence | mailbox metadata source or adapter authority boundary | host / ThreadWeave adapter |
| deep/cyclic crash | graph traversal/serializer guards | ThreadWeave |
| high mailbox CPU/memory | workload dimensions + algorithm path | ThreadWeave/host split |
| CI/coverage failure | exact failing workflow job and test | repository/central workflow owner |
| orphaned Actions workflow identity (registry state outlives deleted YAML) | `scripts/ci/actions_registry_audit.py` report; see ADR-0010 | repository owner/authorized operator |
| independent review failure | exact reviewer evidence job | repository or central reviewer owner |
| release/publish failure | identity/environment/artifact/provenance step | repository/account owner |

## RCA sequence

1. Refetch the exact live repository/PR state; do not trust remembered SHA, base, review, or run IDs.
2. Record contributor head SHA, PR base snapshot SHA, and independently resolved live base tip separately.
3. Open the exact failing job/log or review evidence and identify the first failing step.
4. Check the latest source change that can explain that boundary.
5. Compare with a known working path or previous protected-main behavior.
6. State one testable root-cause hypothesis.
7. Add or identify the smallest regression that fails for that cause.
8. Apply the narrowest source/config/document fix at the owning boundary.
9. Run focused verification, then the full applicable repository quality gate.
10. Refetch exact-head GitHub checks, formal reviews, unresolved threads, mergeability, and live base.
11. Merge only when policy permits; immediately refetch the queue and continue.

## Evidence identity

Do not conflate:

- contributor head;
- GitHub synthetic merge commit;
- PR base snapshot;
- current protected/live base tip;
- predecessor head;
- local checkout;
- workflow materialized merge ref.

A passing result for one identity is not automatically evidence for another. Review/release summaries must name the identity they actually verified.

## Common recovery paths

### Incorrect threading/projection

- preserve the minimal source metadata reproducer;
- verify raw/normalized identifiers separately;
- compare `thread_messages` output before presentation;
- if serializer-only, do not rewrite the canonical graph to compensate;
- add RFC or malformed-input regression at the first defective layer.

### Metadata mismatch

Distinguish **host-provided protocol metadata** from **internal deterministic ordering fallback** before repairing a failure.

- `message_from_email(..., sequence_number=..., uid=...)` carries explicit host-supplied mailbox identifiers. Stale, duplicate, missing, non-positive, or out-of-range host values must be rejected or refreshed at the host/adapter boundary; ThreadWeave must not silently substitute a different protocol identifier.
- Canonical `thread_messages(..., sort_by_sent_date=True)` may use one-based input position only as an internal ordering fallback when an explicit sequence number is absent. That fallback is an ordering key, not host-authoritative IMAP metadata.
- Since protected-main PR #26 (`8af58f141dba00c7251c0ff4a5f7baf4563c8ebd`), `thread_email_messages(...)` leaves public `sequence_number`/UID metadata unset. Default sequence-number or UID serialization therefore fails closed until the host supplies real identifiers, while explicit `message_from_email(..., sequence_number=..., uid=...)` values remain serializable. Preserve this regression whenever adapters or protocol presentation change.

### Performance regression

Reproduce with controlled message count, reference count/depth, sibling width, subject cardinality, ordering flags, and projection size. Correctness/parity digest is mandatory. Do not accept a faster path that changes canonical forest/protocol output.

### CI/reviewer failure

Determine whether failure belongs to ThreadWeave or an organization-central dependency. If central, do not bypass or mutate that repository without authority; preserve the blocker and continue other ThreadWeave work. If local, repair test-first on the active PR branch and re-run exact-head evidence.

### Orphaned Actions workflow identity

Deleting a workflow's YAML from the tree does not disable its independent registry record; GitHub still advertises it as active until explicitly disabled. Do not restore the deleted source and do not disable by filename pattern. Instead:

1. run `scripts/ci/actions_registry_audit.py audit --repository <owner>/<repo> --output <path>` (or read the latest `.github/workflows/actions-registry-audit.yml` scheduled run's uploaded evidence) — the audit itself fails closed if the protected-main branch SHA, live workflow ID set, or open-PR snapshot drifted between its start and end, so a completed run's report is bound to one consistent registry state;
2. re-read the report's `recommended_disable_workflow_ids` — only `orphan_active` records, bound to the exact protected-main SHA and open-PR-head snapshot the audit observed;
3. an authorized operator re-runs the full audit immediately before disabling (not just a spot check of individual IDs) and confirms each ID is still `orphan_active` in that fresh run — state can move between the original audit and the disable action, and a fresh full run also re-detects a new orphan, a re-added workflow, or a moved PR head that a narrower per-ID check would miss;
4. disable only confirmed IDs through the GitHub Actions lifecycle API with an explicit mutation credential; the audit tool itself never holds write authority (ADR-0010);
5. preserve every currently supported workflow (`ci`, `Hourly PR Maintenance`, `Hourly Product Development`, `Release ThreadWeave`, `Actions Registry Audit`, and current security workflows) and record before/after evidence.

### Release failure

Do not manually upload or introduce a long-lived token to bypass Trusted Publishing, provenance, identity, digest, or environment failures. Preserve the last known-good release and repair the failing release authority boundary.

## Communication/evidence record

An incident record should contain:

- incident identifier and bounded impact;
- exact ThreadWeave version/SHA;
- host/environment identifier without unnecessary PII;
- first failing boundary and root cause;
- regression/test added;
- fix commit/PR;
- exact verification evidence;
- rollback/recovery action;
- follow-up prevention item and documentation/ADR update if architecture changed.

## Exit condition

An incident is not closed at "fix committed." It closes when the owning defect is repaired, the regression is green, full applicable exact-head gates are green, integration or rollback evidence is recorded, documentation/ADR is reconciled when needed, and the next repository queue item has been selected.