# ADR-0009: Keep LineageWeave evidence consumption entirely inside the naruon host boundary

**Status:** Proposed
**Date:** 2026-08-22
**Implementation candidate:** PR #20 (`IncrementalThreadIndex`, RFC 8474 EMAILID/THREADID)
**Cross-repository counterpart:** `ContextualWisdomLab/naruon#1437`, `ContextualWisdomLab/LineageWeave#338`

## Context

`naruon#1437` proposes that naruon, as a ThreadWeave host, project selected authorized email/thread evidence into LineageWeave so LineageWeave can reconstruct explainable project-history and predecessor/successor candidates. That issue's "Existing Naruon landing points" section names `naruon#1350` (canonical email identity, dedupe, thread graph, evidence-based resolution) as the identity source naruon must stabilize before any evidence leaves the host.

ThreadWeave has no LineageWeave-related PR or issue of its own: ThreadWeave does not call LineageWeave, does not know LineageWeave exists at runtime, and must not gain that knowledge. The only real dependency is architectural: naruon's `#1350` identity work is expected to sit on top of ThreadWeave's threading output, and the RFC 8474 EMAILID/THREADID stable-identity contract proposed in ADR-0004 / PR #20 is the most natural stable key a host would echo into any downstream evidence projection (LineageWeave's or otherwise). Without a written decision, a future contributor could be tempted to let ThreadWeave call an HTTP evidence API, accept a LineageWeave SDK as a runtime dependency, or treat inferred lineage relations as thread-structural truth — each of which would violate ADR-0001 through ADR-0004 and `docs/PRD.md`'s zero-runtime-dependency/standalone-library requirement.

## Decision

ThreadWeave remains completely unaware of LineageWeave. This ADR records, as a boundary decision rather than a new capability, that:

1. ThreadWeave exposes only its existing typed surface — `thread_messages`, `thread_email_messages`, IMAP `THREAD`/`UID THREAD` serialization, and, once ADR-0004 is Accepted, `IncrementalThreadIndex` snapshots with RFC 8474 EMAILID/THREADID values (Gondwana, 2018). It does not add a LineageWeave adapter, evidence-export format, or network call.
2. Any Message-ID / References / In-Reply-To evidence, provider thread reference, or stable EMAILID/THREADID that naruon forwards to LineageWeave under `naruon#1437` is naruon's own projection of ThreadWeave's public output — produced after naruon's `#1350` canonicalization, not a ThreadWeave-owned export.
3. ThreadWeave structural output (`thread_messages` results, RFC 5256 grouping, sent-date order) remains the correctness oracle for *thread structure*. LineageWeave-inferred predecessor/successor or project-lineage relations are a separate, host-owned inference layer and must never be represented in ThreadWeave documentation, tests, or code as thread-structural fact.
4. ThreadWeave's stable-identity work (ADR-0004) is prioritized as leverage for this cross-repository chain: a host cannot hand LineageWeave a durable, replay-safe evidence key without a stable EMAILID/THREADID that survives incremental mailbox changes. This ADR does not change ADR-0004's acceptance conditions or its Draft-until-issue-#17 release gate; it only records why that work has consumer value beyond naruon's own mailbox state.

## Consequences

- No ThreadWeave source change is required by `naruon#1437`. This ADR is documentation-only.
- `docs/product-technical-gap-baseline.md` tracks the cross-repository dependency chain (`naruon#1437` → `LineageWeave#338` → ThreadWeave PR #20) so the gap is visible without ThreadWeave taking on LineageWeave's authority or persistence.
- If a future PR proposes a direct ThreadWeave→LineageWeave integration, network call, or shared schema, it conflicts with this ADR and with ADR-0001/ADR-0002 and must supersede this record explicitly rather than being added silently.

## References

Gondwana, B. (2018). *IMAP extension for object identifiers* (RFC 8474). RFC Editor. https://doi.org/10.17487/RFC8474
