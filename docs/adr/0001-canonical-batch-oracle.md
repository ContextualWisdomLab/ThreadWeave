# ADR-0001: Preserve one canonical batch threading oracle

**Status:** Accepted  
**Date:** 2026-08-09

## Context

Reference threading combines container identity, reference precedence, cycle
prevention, dummy pruning, optional subject grouping, and optional sent-date
ordering. Reimplementing those rules in protocol adapters, incremental state, or
host integrations would create multiple correctness definitions and make parity
difficult to prove.

The container model is the algorithm Zawinski (1997–2002) documented for
Netscape Mail and News 2.0/3.0: map each `Message-ID` to a container, link
parent/child edges from the reference chain, gather parentless containers as
roots, and prune empty containers so a missing root can still group its
descendants. RFC 5256 later standardized that approach as the IMAP `REFERENCES`
threading algorithm and recorded the historical dependence explicitly
(Crispin & Murchison, 2008, Introduction historical note; informative reference
`[THREADING]`).

RFC 5256 §2 also fixes the structural steps that a second implementation would
be tempted to “simplify”:

- link the complete valid `References` chain without stealing an existing good
  parent;
- when that chain is unavailable, use only the first valid `In-Reply-To`
  identifier as the parent, because later tokens are often addresses rather than
  message identifiers;
- prune empty childless containers, splice-promote empty internal containers,
  and retain a multi-child dummy at the root as a missing-thread-root grouping
  node.

RFC 5322 §3.6.4 supplies the identification-field grammar (`Message-ID`,
`In-Reply-To`, `References`, `msg-id`) that those linking rules consume
(Resnick, 2008). Optional subject grouping and sent-date ordering are later
policy stages of the same RFC 5256 algorithm; they are not a second oracle.

## Decision

`thread_messages` and the batch graph/container implementation are the sole structural correctness oracle. Adapters normalize input into that oracle. IMAP code projects its result without mutating or reconstructing it. An incremental layer may optimize which connected components are recomputed, but affected components must still pass through the canonical batch algorithm.

## Consequences

- One set of RFC/JWZ structural tests defines correctness.
- Performance work may optimize indexing, partitioning, projection, and caching but cannot introduce a second thread-construction algorithm.
- Incremental/full-rebuild parity is a release gate for incremental work.
- A future replacement algorithm requires a superseding ADR and side-by-side truth-recovery evidence, not a silent refactor.

## References

Crispin, M., & Murchison, K. (2008). *Internet Message Access Protocol—SORT and
THREAD extensions* (RFC 5256). RFC Editor. https://doi.org/10.17487/RFC5256

Resnick, P. (Ed.). (2008). *Internet Message Format* (RFC 5322). RFC Editor.
https://doi.org/10.17487/RFC5322

Zawinski, J. (1997–2002). *Message threading*.
https://www.jwz.org/doc/threading.html
