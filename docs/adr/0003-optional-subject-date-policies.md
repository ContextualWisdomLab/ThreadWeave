# ADR-0003: Keep subject grouping and sent-date ordering explicit policies

**Status:** Accepted  
**Date:** 2026-08-09

## Context

RFC-grounded subject grouping and sent-date ordering are useful for protocol-compatible presentation, but changing historical defaults can reorder existing callers' results. Subject equality is also weaker evidence than explicit reference headers.

## Decision

Reference threading remains authoritative. Subject fallback grouping is opt-in. RFC sent-date ordering is opt-in through `sort_by_sent_date`; first-appearance behavior remains the compatibility default. When enabled, the implementation uses the documented RFC 5256 normalization/order rules and explicit mailbox sequence-number tie-breaking.

## Consequences

- Existing callers do not receive silent reordering or subject-based merging.
- Standards-compatible hosts can explicitly request the richer policy.
- Tests must cover both option states and prove reference relationships are not weakened by subject grouping.
- Future default changes require a versioned compatibility decision and migration guidance.