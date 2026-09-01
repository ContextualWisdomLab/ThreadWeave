# ThreadWeave Incident and RCA Runbook

**Status:** Accepted repository-operating guidance  
**Last reviewed:** 2026-09-01

ThreadWeave is a library, so incidents generally present as incorrect thread structure, malformed protocol output, resource exhaustion, package/release failure, or repository automation/security failure inside a consuming host or delivery pipeline.

## Incident principles

- Restore evidence before changing code: record exact package/commit, bounded reproducer, options, host metadata class, failing check/run/job, and the first observable incorrect boundary.
- **Fix the owning layer** rather than compensating downstream.
- Reproduce with a failing regression before a behavior fix when repository code is at fault.
- Never relax a correctness/security/coverage/review gate to make an incident disappear.
- **A queued or externally unavailable reviewer/check is an item-local state**; continue other safe repository work while periodically refetching it.
- Registry credentials are authority, never diagnostics: do not print, echo, fingerprint into evidence, or move them into a broader job to debug publication.

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
| orphaned Actions workflow identity | merged PR #32 audit evidence / ADR-0010 | repository owner / authorized operator |
| independent review failure | exact reviewer evidence job | repository or central reviewer owner |
| new release cannot start | release-readiness/version/public-version/publisher availability | repository release boundary |
| PyPI authentication failure | isolated `publish-pypi` job | repository publisher / organization secret authority |
| PyPI digest/install verification failure | public registry artifact verification | release pipeline / registry evidence |

## RCA sequence

1. Refetch exact live repository/PR state; do not trust remembered SHA, base, review, or run IDs.
2. Record **contributor head** SHA, **PR base snapshot** SHA, and independently resolved **current protected/live base tip** separately.
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

Do not conflate contributor head, GitHub synthetic merge commit, PR base snapshot, current protected/live base tip, predecessor head, local checkout, or workflow materialized merge ref. A passing result for one identity is not automatically evidence for another.

## Common recovery paths

### Incorrect threading/projection

Preserve the minimal source metadata reproducer, verify raw/normalized identifiers separately, compare `thread_messages` output before presentation, and add the regression at the first defective layer. If the defect is serializer-only, do not rewrite the canonical graph to compensate.

### Metadata mismatch

Distinguish **host-provided protocol metadata** from **internal deterministic ordering fallback** before repairing a failure.

- `message_from_email(..., sequence_number=..., uid=...)` carries explicit host-supplied mailbox identifiers. Stale, duplicate, missing, non-positive, or out-of-range host values must be rejected or refreshed at the host/adapter boundary; ThreadWeave must not invent replacements.
- Canonical `thread_messages(..., sort_by_sent_date=True)` may use **one-based input position only as an internal ordering fallback** when an explicit sequence number is absent. That fallback is not public IMAP metadata.
- Since **protected-main PR #26**, `thread_email_messages(...)` **leaves public `sequence_number`/UID metadata unset**. Default public identifier serialization therefore fails closed until the host supplies real identifiers.

### Performance regression

Reproduce with controlled message count, reference count/depth, sibling width, subject cardinality, ordering flags, and projection size. Correctness/parity digest is mandatory. Do not accept a faster path that changes canonical forest/protocol output.

### CI/reviewer failure

Determine whether failure belongs to ThreadWeave or an organization-central dependency. If central, preserve the blocker and continue other safe work. If local, repair test-first on the active PR branch and reacquire exact-head evidence.

### Orphaned Actions workflow identity

Deleting workflow YAML does not disable its independent Actions registry record. Use the merged PR #32 `scripts/ci/actions_registry_audit.py` evidence, rerun the complete audit immediately before mutation, and disable only records still classified `orphan_active` through an authorized operator credential. The detector remains read-only under ADR-0010. Preserve current supported CI/hourly/release/security workflows.

### Release readiness failure

If a new reviewed package version is absent from PyPI but the approved publisher is unavailable, fail before build, tag, or GitHub Release side effects. The current approved publisher is the organization `PIPY_TOKEN` secret, but readiness may observe only the boolean fact that it is available; the token value belongs solely to the pinned PyPA publisher action.

Do not add `PIPY_USERNAME` merely to debug token publication: API-token mode uses the standard `__token__` username and deliberately minimizes credential exposure. Do not switch silently to Trusted Publishing or another credential after an authentication failure; changing publisher mode is a reviewed release-authority change.

### Release failure after immutable GitHub evidence

If build/attestation/tag/GitHub Release succeeded but PyPI authentication fails, preserve the exact tag/release/artifact bundle, repair the approved publisher authority, and retry the same exact protected release head. The tag and GitHub Release paths are idempotent verification paths and must not be rewritten.

If PyPI upload succeeded but public filename/SHA-256 or clean-install verification fails, do not republish the same version. Preserve the public artifact and reviewed bundle, classify whether the mismatch belongs to registry publication, evidence generation, or verification, and fix the owning layer. PyPI versions/files are immutable; a genuinely defective release is superseded by a new reviewed patch version and may be yanked when appropriate.

Manual workstation upload is not a recovery path. Neither is weakening digest/provenance/review protection, using `skip-existing`, or moving the registry token into shell/debug output.

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
- for release incidents, publisher mode name and public artifact digests but never credential material;
- follow-up prevention item and documentation/ADR update when architecture changed.

## Exit condition

An incident is not closed at “fix committed.” It closes when the owning defect is repaired, the regression is green, full applicable exact-head gates are green, integration or rollback evidence is recorded, documentation/ADR is reconciled when needed, and the next repository queue item has been selected.
