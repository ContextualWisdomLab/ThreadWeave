# ADR-0001: Preserve one canonical batch threading oracle

**Status:** Accepted  
**Date:** 2026-08-09

## Context

Reference threading combines container identity, reference precedence, cycle prevention, dummy pruning, optional subject grouping, and optional sent-date ordering. Reimplementing those rules in protocol adapters, incremental state, or host integrations would create multiple correctness definitions and make parity difficult to prove.

## Decision

`thread_messages` and the batch graph/container implementation are the sole structural correctness oracle. Adapters normalize input into that oracle. IMAP code projects its result without mutating or reconstructing it. An incremental layer may optimize which connected components are recomputed, but affected components must still pass through the canonical batch algorithm.

## Consequences

- One set of RFC/JWZ structural tests defines correctness.
- Performance work may optimize indexing, partitioning, projection, and caching but cannot introduce a second thread-construction algorithm.
- Incremental/full-rebuild parity is a release gate for incremental work.
- A future replacement algorithm requires a superseding ADR and side-by-side truth-recovery evidence, not a silent refactor.