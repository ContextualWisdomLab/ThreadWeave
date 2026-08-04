# Incremental Thread Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an atomic, snapshot-capable incremental mailbox index that recomputes only affected reference/subject components while remaining exactly equivalent to the existing batch threader.

**Architecture:** A new `threadweave.incremental` module owns caller keys, copied message metadata, reverse connectivity buckets, component-local batch results, projections, deltas, and snapshot validation. Existing batch/thread/container/IMAP modules remain transport-neutral and authoritative. The release-frozen `main` branch is not modified until release blocker #17 closes.

**Tech Stack:** Python 3.10-3.13 standard library, existing `Message`, `Container`, `thread_messages`, RFC parsing/collation/date helpers, pytest, coverage, Ruff, Hatchling.

## Global Constraints

- Runtime dependencies remain empty.
- Production statement and branch coverage remain 100%.
- Every authored production module, class, function, method, and property has a beginner-readable docstring.
- Graph processing is iterative and identity-safe.
- Caller payloads never enter snapshots, delta equality, logs, or error messages.
- RFC 7162, RFC 8474, RFC 8621, RFC 9051, and existing RFC 5256 behavior remain traceable in APA 7th documentation.
- The PR remains draft and unmerged while issue #17 is open.

---

### Task 1: Public change, projection, and error contracts

**Files:**
- Create: `src/threadweave/incremental.py`
- Create: `tests/test_incremental_contract.py`
- Modify: `src/threadweave/__init__.py`
- Modify: `tests/test_documentation.py`

**Interfaces:**
- Produces: `IndexedMessage`, `MailboxChangeSet`, `ThreadProjection`, `ThreadDelta`, `IncrementalThreadError`, `VersionConflictError`, `ExternalIdentityError`, `IncrementalThreadIndex`.

- [ ] Write failing import, constructor-default, immutable-record, invalid-key, disjoint-change-set, and docstring tests.
- [ ] Run the focused tests and confirm missing symbols fail.
- [ ] Implement frozen public records, bounded key validation, exception hierarchy, and empty index properties.
- [ ] Export the new API and include the module in documentation inspection.
- [ ] Run focused tests and commit.

### Task 2: Atomic record validation and copied metadata

**Files:**
- Modify: `src/threadweave/incremental.py`
- Create: `tests/test_incremental_atomicity.py`

**Interfaces:**
- Consumes: Task 1 public records.
- Produces: `IncrementalThreadIndex.apply(change_set) -> ThreadDelta` for record ownership and versioning before graph behavior.

- [ ] Write failing tests for additions, replacement-in-place, removal, disjoint keys, missing/existing ownership errors, boolean/negative version values, and optimistic conflicts.
- [ ] Add tests proving payload identity is retained in memory while reference sequences are copied and later caller mutation cannot change indexed metadata.
- [ ] Run focused tests and confirm failures.
- [ ] Implement validation on copied state and commit only after every input passes.
- [ ] Verify failures leave version, records, roots, and projections unchanged.
- [ ] Run focused tests and commit.

### Task 3: Connectivity indexes and bounded component recomputation

**Files:**
- Modify: `src/threadweave/incremental.py`
- Create: `tests/test_incremental_components.py`

**Interfaces:**
- Produces: token extraction, reverse buckets, component membership, component-local roots, affected-message reporting.

- [ ] Write failing batch-parity tests for independent roots, linear references, shared missing roots, delayed ancestors, duplicate Message-IDs, replacement, root/internal/leaf removal, and bridge merges.
- [ ] Add a spy around the module-level batch delegate proving an unrelated component is not passed to the delegate during a one-component update.
- [ ] Run focused tests and confirm failures.
- [ ] Implement normalized ID/reference/subject tokens, copied reverse buckets, old-component seeding, touched-token expansion, iterative repartition, and component-local `thread_messages` calls.
- [ ] Compose roots in global insertion order and produce deterministic projections.
- [ ] Run focused tests and commit.

### Task 4: Sent-date, subject, IMAP, and deep-tree parity

**Files:**
- Modify: `src/threadweave/incremental.py`
- Create: `tests/test_incremental_parity.py`

**Interfaces:**
- Consumes: Task 3 component state.
- Produces: exact output parity for both batch options and protocol serialization.

- [ ] Write failing tests for RFC 5051 subject grouping, RFC 5256 sent-date ordering, explicit/implicit sequence collisions, Unicode subjects, raw headers, UID THREAD output, and one-shot source construction.
- [ ] Add deep-chain, split-tree, and malformed cycle-oriented metadata cases without recursive index traversal.
- [ ] Run focused tests and confirm failures.
- [ ] Implement global effective-sequence validation, root ordering from the first concrete node, and deterministic root composition.
- [ ] Compare projections and RFC 5256 serialization with complete batch rebuilds.
- [ ] Run focused tests and commit.

### Task 5: RFC 8474 external identity transitions

**Files:**
- Modify: `src/threadweave/incremental.py`
- Create: `tests/test_incremental_identity.py`

**Interfaces:**
- Produces: immutable EMAILID/THREADID validation and explicit merge/split groups in `ThreadDelta`.

- [ ] Write failing tests for replacement changes/removal of reported IDs, same EMAILID with inconsistent/missing THREADID, structurally merged distinct IDs, and structural splits.
- [ ] Run focused tests and confirm failures.
- [ ] Implement cross-record identity validation and deterministic overlap-based transition classification.
- [ ] Ensure no canonical thread ID is invented and sequence numbers never participate in identity.
- [ ] Run focused tests and commit.

### Task 6: JSON-safe snapshot and restore

**Files:**
- Modify: `src/threadweave/incremental.py`
- Create: `tests/test_incremental_snapshot.py`

**Interfaces:**
- Produces: `snapshot()` and `IncrementalThreadIndex.restore(...)` schema version 1.

- [ ] Write failing deterministic round-trip tests covering strings, aware/naive datetimes, references, options, external IDs, and payload omission.
- [ ] Write failing tests for unknown/missing/extra fields, duplicate keys, invalid types, noncanonical records, oversized record counts/bytes, and unsupported schema versions.
- [ ] Run focused tests and confirm failures.
- [ ] Implement tagged date encoding, strict field readers, JSON-size checks, restore through validated records, and derived-state rebuild.
- [ ] Run focused tests and commit.

### Task 7: Buyer and research documentation, changelog, package smoke

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/research/README.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `AGENTS.md`
- Modify: PR body

**Interfaces:**
- Documents public behavior, complexity boundary, release freeze, and standards.

- [ ] Add a complete incremental example with atomic changes, delta inspection, snapshot/restore, and RFC 8474 identity notes.
- [ ] Add APA 7th references and explicitly separate caller IDs from managed policy.
- [ ] Add `[Unreleased]` notes without changing version `0.2.0`.
- [ ] Extend the installed-wheel smoke test to construct and update an index.
- [ ] Add invariants to `AGENTS.md`.
- [ ] Run all repository checks and commit.

### Task 8: Exact-head review and merge gating

**Files:**
- No product files unless a review or check identifies a defect.

- [ ] Run lock regeneration, Ruff, compileall, doctests, full pytest/coverage, autonomous/release-boundary coverage, build, hash-installed wheel smoke, SAST, and Security Scan.
- [ ] Confirm all production and trusted-boundary statements/branches are 100% covered.
- [ ] Review every unresolved thread and apply focused fixes.
- [ ] Keep the PR draft while issue #17 is open; do not enable auto-merge.
- [ ] After the verified `0.2.0` release closes #17, rebase/update the exact head, rerun all gates, request independent review, and merge only when policy is satisfied.
