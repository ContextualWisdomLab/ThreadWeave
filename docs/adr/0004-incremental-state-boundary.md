# ADR-0004: Add incremental state only as a batch-oracle-preserving extension

**Status:** Proposed  
**Date:** 2026-08-09  
**Implementation candidate:** PR #20

## Context

A full mailbox rebuild after every arrival, expunge, or metadata correction is expensive for large mailboxes. However, an independent incremental threading algorithm would duplicate standards logic and could diverge from the batch result. Durable state also introduces versioning, concurrency, identity, snapshot, and host-ownership questions.

The structural truth remains the JWZ container model as standardized by RFC 5256
`REFERENCES` (Zawinski, 1997–2002; Crispin & Murchison, 2008). ADR-0001 already
requires every affected component to pass through that batch oracle. An
incremental index may remember which components changed; it may not invent a
second parent-selection, dummy-pruning, or subject-grouping procedure.

RFC 8474 defines persistent IMAP object identifiers: `EMAILID` uniquely
identifies identical message content and is immutable once reported; `THREADID`
correlates related messages and MUST NOT change after the server reports it
(Gondwana, 2018, §5). Those values are host-owned mailbox identities. ThreadWeave
may validate them as external identifiers and must not silently rewrite them to
repair threading. Sequence numbers and UIDs remain caller-supplied protocol
metadata under RFC 9051 `nz-number` / `uniqueid` rules (Melnikov & Leiba, 2021).

ThreadWeave remains a leaf standard-library package. Naruon or another host may
persist a documented snapshot under its own durable transaction boundary. This
ADR does not create a ThreadWeave database.

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

## References

Crispin, M., & Murchison, K. (2008). *Internet Message Access Protocol—SORT and
THREAD extensions* (RFC 5256). RFC Editor. https://doi.org/10.17487/RFC5256

Gondwana, B. (Ed.). (2018). *IMAP Extension for Object Identifiers* (RFC 8474).
RFC Editor. https://doi.org/10.17487/RFC8474

Melnikov, A., & Leiba, B. (Eds.). (2021). *Internet Message Access Protocol
(IMAP)—Version 4rev2* (RFC 9051). RFC Editor.
https://doi.org/10.17487/RFC9051

Zawinski, J. (1997–2002). *Message threading*.
https://www.jwz.org/doc/threading.html
