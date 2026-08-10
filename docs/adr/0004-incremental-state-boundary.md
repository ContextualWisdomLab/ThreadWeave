# ADR-0004: Add incremental state only as a batch-oracle-preserving extension

**Status:** Proposed  
**Date:** 2026-08-09  
**Implementation candidate:** PR #20

## Context

A full mailbox rebuild after every arrival, expunge, or metadata correction is expensive for large mailboxes. However, an independent incremental threading algorithm would duplicate standards logic and could diverge from the batch result. Durable state also introduces versioning, concurrency, identity, snapshot, and host-ownership questions.

## Proposed decision

Introduce a process-local `IncrementalThreadIndex` that uses stable caller-owned message keys, optimistic versions, atomic change sets, bounded affected-component indexes, explicit merge/split deltas, and payload-free versioned snapshots. Every affected structural component is rebuilt by the canonical batch oracle. RFC 8474 EMAILID/THREADID values are validated as external identities and are never silently rewritten.

ThreadWeave would still not own database persistence, tenancy, authentication, distributed locking, or mailbox synchronization. Hosts may persist a documented snapshot and optimistic version under their own durable transaction boundary.

## Acceptance conditions

This ADR becomes `Accepted` only when an implementing PR lands on protected `main` with:

- randomized incremental/full-rebuild structural parity;
- atomic rollback and optimistic-version conflict tests;
- hostile snapshot schema/type/depth/size tests;
- RFC 8474 identity consistency tests;
- same-index concurrency tests;
- mailbox-scale performance evidence with exact parity digest;
- 100% production statement/branch coverage and docstrings;
- current-head CI/security/review acceptance.

## Consequences if accepted

Small mailbox deltas can avoid rebuilding unrelated reference components while structural truth remains centralized. Hosts gain a reusable state handoff but remain responsible for durable concurrency and persistence.