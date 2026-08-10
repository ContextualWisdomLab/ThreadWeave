# ADR-0003: Keep subject grouping and sent-date ordering explicit policies

**Status:** Accepted  
**Date:** 2026-08-09

## Context

RFC-grounded subject grouping and sent-date ordering are useful for protocol-compatible presentation, but changing historical defaults can reorder existing callers' results. Subject equality is also weaker evidence than explicit reference headers.

## Decision

Reference threading remains authoritative. Subject fallback grouping is opt-in. RFC sent-date ordering is opt-in through `sort_by_sent_date`; first-appearance behavior remains the compatibility default. When ordering is enabled, the implementation uses the documented RFC 5256 date normalization/order rules. An explicit `sequence_number` is validated as a positive mailbox sequence number; when it is absent, the one-based input position is used only as an internal ordering fallback. The resulting effective ordering sequence values must be unique across all sorted messages. Input position is never inferred, exposed, or persisted as a public IMAP sequence number.

## Consequences

- Existing callers do not receive silent reordering or subject-based merging.
- Standards-compatible hosts can explicitly request the richer policy.
- Hosts that need public IMAP sequence-number serialization still supply and validate real mailbox identifiers at the presentation boundary; the ordering fallback does not create them.
- Tests must cover explicit sequence numbers, omitted-sequence fallback, duplicate effective values, both option states, and prove reference relationships are not weakened by subject grouping.
- Future default changes require a versioned compatibility decision and migration guidance.