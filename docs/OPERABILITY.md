# ThreadWeave Operability, Integration, and Recovery Guide

**Status:** Accepted for library operation and repository delivery.  
**Last reviewed:** 2026-09-01

ThreadWeave is a library, not an always-on service. Operability therefore means predictable resource behavior, integration observability, deterministic failures, reproducible packaging, and a safe release/rollback path. Host services own service SLOs, persistence, tenancy, distributed coordination, backups, and incident response for mailbox data.

## Runtime operating model

### Embedded mode

Import `threadweave` into a host process and call public functions directly. No daemon, network endpoint, database, or background worker is required.

### Host-wrapped mode

A mail server, naruon, or other service may expose ThreadWeave through its own API or worker. The host must provide:

- authentication/authorization and tenant isolation;
- mailbox data access and lifecycle;
- sequence-number/UID metadata;
- request size/rate/concurrency controls;
- audit and tracing;
- timeout/cancellation policy;
- durable versioning/locking if incremental state is adopted.

## Capacity dimensions

Relevant workload dimensions include message count, normalized reference count, maximum reference depth, sibling width, subject-group cardinality, date-ordering option, search-result projection size, and protocol serialization depth. Measure these explicitly in host telemetry rather than reporting only elapsed time.

## Failure classes

| Class | Example | Operator/host response |
|---|---|---|
| input defect | malformed header/identifier/date | record bounded diagnostic; quarantine/repair source metadata if business policy permits |
| structural defect | invalid cycle/shared source graph passed to serializer | reject operation; investigate host mutation or adapter bug |
| mailbox metadata defect | duplicate sequence/UID, missing UID | refresh/reconcile mailbox metadata; do not invent identifiers |
| resource pressure | unusually large/deep mailbox | apply host request budget; benchmark/partition at host boundary; do not weaken correctness |
| package regression | failing RFC/parity/coverage test | stop rollout and revert package version |
| automation/security failure | cancelled/failed required CI/security gate | no merge/release; RCA exact failing boundary |
| publisher unavailable | new public version required but approved publisher credential is unavailable | fail before new build/tag/GitHub Release side effects; restore publisher authority without exposing credentials |
| registry authentication failure | isolated PyPI publisher rejects the approved credential after immutable GitHub evidence exists | preserve tag/release, repair publisher authority, and retry the same exact release head idempotently; never rewrite evidence |
| public-artifact mismatch | PyPI filename/SHA-256 set differs from reviewed bundle | stop completion, preserve immutable evidence, investigate registry/pipeline identity; never republish the same version/files |

## Observability guidance for hosts

Do not log raw message bodies or complete headers merely to observe ThreadWeave. Prefer bounded metadata such as:

- package version/commit;
- operation type and options;
- message count;
- reference count/depth summary;
- root/thread count;
- elapsed time;
- serialization result length;
- bounded failure class;
- host correlation ID;
- incremental expected/new version and affected-count if that feature is adopted.

Subjects and Message-IDs can be PII and should be logged only under an explicit purpose and retention policy.

Publisher credentials are never observability data. Logs and release receipts may record the selected publisher mode name, exact source/tag/release identity, artifact hashes, workflow/run identity, and public verification result, but never `PIPY_TOKEN` or any credential-derived representation.

## Performance acceptance

Performance changes are accepted only with correctness parity. The current core favors deterministic correctness and iterative safety. Mailbox-scale benchmarks should compare the exact output/projection digest and record workload, runtime, and peak memory metrics.

For PR #20, incremental benchmark evidence is active-PR evidence only. Re-run after rebasing/merging prerequisites and again on the final integration head before converting those claims to protected-main operating guidance.

## Concurrency

Current protected-main batch calls are ordinary independent function calls; caller concurrency follows Python process/thread semantics and caller-owned object safety. ThreadWeave does not provide distributed synchronization.

The proposed incremental index uses process-local serialization plus optimistic versions. If accepted, a multi-process host must persist the version and serialize durable mutations itself; the library lock is not sufficient for distributed correctness.

## Upgrade procedure

1. Read CHANGELOG and relevant ADR/API changes.
2. Run the host's integration fixtures against the candidate package.
3. Verify thread/protocol outputs for representative mailbox samples.
4. For any persisted host cache/snapshot, validate format compatibility before rollout.
5. Canary the package in a bounded host environment if the host is stateful/high-impact.
6. Monitor failure rates, thread counts, latency, and memory against the previous version.
7. Expand only after no correctness regression is observed.

## Rollback

Because current ThreadWeave owns no persistence, runtime rollback is normally a package-version rollback to the previous known-good artifact. Hosts must avoid destructive migration of their own data based solely on a new thread projection.

If incremental snapshots become public, rollback must consider snapshot schema compatibility. A host should retain the last known-good snapshot/version or reconstruct state from canonical messages when safe; snapshot migration must never overwrite the only durable copy without rollback evidence.

PyPI versions/files and immutable release identities are not rollback scratch space. A defective published release should be superseded by a new reviewed patch version (and yanked where appropriate), never replaced in place.

## Release procedure

A release requires:

- exact protected-head version and CHANGELOG alignment with no material final-release notes stranded under `Unreleased`;
- required CI/SAST/security/review gates passing;
- reproducible/reviewed CI dependency lock;
- fresh wheel/sdist build;
- package metadata and `py.typed` checks;
- outside-source wheel installation/smoke;
- artifact hashes plus configured SLSA/SPDX provenance;
- approved publisher availability before new irreversible release work;
- isolated PyPI publication using the selected publisher mode;
- public PyPI filename/SHA-256 equality with the reviewed release bundle;
- post-publication clean install and representative `THREAD`/`UID THREAD` smoke.

The current publisher mode is the organization GitHub Secret `PIPY_TOKEN`, passed only to the pinned PyPA publishing action. `PIPY_USERNAME` is not required and is not materialized. PyPI Trusted Publishing remains an optional future publisher mode, not a release prerequisite.

Do not mark a release complete merely because a PR merged, a tag exists, or a GitHub Release exists. The public package and its verified artifact identity are the buyer-visible completion boundary.

## Incident RCA

For every deterministic failure, identify the first failing layer: adapter/header parsing, canonical graph, subject/collation, date ordering, IMAP projection, host metadata, packaging, workflow, reviewer/security gate, release readiness, registry publisher, or public-artifact verification. Fix the owning layer and add a regression there. Avoid compensating in downstream presentation for an upstream graph defect.

## Disaster recovery boundary

ThreadWeave has no database backup to restore. The host's source mailbox data is the authoritative recovery source. If caches/projections/snapshots are lost, regenerate them from authorized canonical host metadata using a known-good ThreadWeave version. Host repositories must document their own backup/RPO/RTO separately.

## Repository automation

Hourly PR maintenance, exact-head verification, writer-boundary, NIM broker, and token-setup procedure live in [`docs/operations/hourly-autonomous-maintenance.md`](operations/hourly-autonomous-maintenance.md). That playbook is not a runtime operating dependency for `pip install threadweave` or host composition through `from threadweave import thread_messages`.
