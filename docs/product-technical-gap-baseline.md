# ThreadWeave Product/Technical Gap Baseline

**Status:** Living document — reconcile on every PR merge, release, or cross-repository dependency change  
**Last reviewed:** 2026-09-01

Read this first when deciding what to work on next in ThreadWeave. It records the current release gate, active product work, merged operational evidence, and the one confirmed cross-repository dependency chain so work lands in the correct bounded context instead of duplicating another repository's responsibility.

## How to use this document

1. Refetch protected `main`, open PRs/issues, and exact current-head checks before acting on a row.
2. Before opening a new PR, verify that the gap is not already owned here or by another CWL bounded context.
3. Before merging a PR, update the row it changes so the next contributor does not re-investigate solved work.
4. For cross-repository gaps, record exact dependency edges and owners; do not copy implementation across repositories merely to avoid waiting on a dependency.

## Current release lane

| Item | Current state | Blocking dependency | Next action |
|---|---|---|---|
| [PR #35](https://github.com/ContextualWisdomLab/ThreadWeave/pull/35) | Active release-authority repair for `0.2.0`; changes the OIDC-only publisher to the approved organization `PIPY_TOKEN` path, makes protected-main release changelog/version-driven, and adds public PyPI digest + clean-install verification | Exact PR-head CI/SAST/Security/review/merge gates only. External PyPI Trusted Publisher setup is no longer required for the approved API-token mode. | Resolve valid current-head findings, require terminal-success exact-head checks, merge through protected `main`, then observe the automatic release workflow. Close #17 only after PyPI wheel/sdist digest equality and clean-install `THREAD`/`UID THREAD` smoke succeed. |
| [Issue #17](https://github.com/ContextualWisdomLab/ThreadWeave/issues/17) | Release acceptance record for public `0.2.0`; policy corrected 2026-09-01 to accept organization GitHub Secret `PIPY_TOKEN` | PR #35 must integrate and the resulting exact protected-main release workflow must publish and verify the public artifact | Do not manually upload or rewrite release evidence. Use the reviewed publisher job and close only after public-artifact proof. |

The organization also has `PIPY_USERNAME`, but ThreadWeave deliberately does not materialize it: the pinned PyPA action's API-token mode uses the conventional `__token__` username. Secret values are never evidence and must not appear in logs, outputs, artifacts, provenance, caches, or release receipts.

## Active product work

| PR / issue | State | Blocking dependency | Next action |
|---|---|---|---|
| [PR #20](https://github.com/ContextualWisdomLab/ThreadWeave/pull/20) | Draft incremental mailbox threading with stable identity handoff; **IMPLEMENTED-ON-ACTIVE-PR**, not protected-main behavior | Issue #17 must close through verified `0.2.0` publication first; the branch must then be refreshed onto released protected main and revalidated | After #17 closes, reconcile conflicts without force-push shortcuts, rerun Python 3.10–3.14, exact coverage/docstrings, randomized batch parity and mailbox-scale evidence, obtain current-head independent review, then merge normally. |
| [Issue #22](https://github.com/ContextualWisdomLab/ThreadWeave/issues/22) | Hourly product-development incident has only its final bounded model-path proof remaining | Genuine release/PR queue state must permit the proof; do not manufacture an empty queue | Re-evaluate after #17 and the truthful PR queue permit model-backed development. |
| [Issue #31](https://github.com/ContextualWisdomLab/ThreadWeave/issues/31) | Orphaned GitHub Actions workflow-identity cleanup | The repository-owned detector from merged PR #32 is available; mutation of GitHub control-plane identities remains an authorized operator action | Use the merged detector evidence to disable only confirmed orphan identities; preserve supported CI/hourly/release/security workflows. |

## Recently integrated operational foundations

The following are no longer open implementation PRs, but they remain important release and operability evidence:

- **PR #32** merged the read-only Actions registry lifecycle detector and its exact classification/pagination/drift checks. It is the repository-owned evidence source for issue #31; it does not itself gain workflow-disable authority.
- **PR #34** merged this product/technical gap baseline and ADR-0009's LineageWeave consumer-boundary documentation.
- **PR #30** integrated the original fail-before-side-effects release preflight. PR #35 supersedes its OIDC-only publisher assumption while preserving the core invariant that an unavailable publisher must be detected before new release side effects.
- `.github` provider/reviewer incidents that had historically blocked #32/#34 are not current ThreadWeave release blockers and must not be reintroduced into the current release diagnosis without fresh live evidence.

## Release-readiness truth table

| Condition | Release behavior |
|---|---|
| protected `main`; reviewed version absent from PyPI; `PIPY_TOKEN` available; current release gates pass | build → attest → immutable tag → GitHub Release → PyPI publish → public digest/install verification |
| reviewed version already exists on PyPI | no new publication; preserve immutable public version and treat the automatic trigger as a no-op |
| new version required but approved publisher unavailable | fail before build/tag/GitHub Release side effects |
| changelog has material `Unreleased` notes for the requested final version | fail closed until notes are moved into the dated release section |
| tag/release exists but points to or contains different evidence | fail closed; never rewrite or clobber |
| PyPI upload succeeds but verification fails | preserve immutable public artifacts, investigate, and retry verification; never republish the same filename/version |

## Cross-repository gap: LineageWeave evidence consumption (`naruon#1437`)

**ThreadWeave has no production-integration PR or issue that mentions LineageWeave** as a direct runtime dependency. ADR-0009 (Proposed) records that this separation is intentional. The actual dependency graph runs through naruon, which owns host-level projection and integration:

```text
ContextualWisdomLab/naruon#1437
  → depends on naruon#1350
    → depends on ThreadWeave PR #20 stable/replay-safe incremental identity
  → also depends on ContextualWisdomLab/LineageWeave#338
```

Relation-level statement: `naruon#1437` depends on `naruon#1350`, which depends on ThreadWeave PR #20; `naruon#1437` also depends on `LineageWeave#338` as a separate branch, not as a transitive step through `naruon#1350`.

ThreadWeave therefore must not add a LineageWeave HTTP adapter, database coupling, or runtime dependency merely to shorten the chain. The reusable responsibility here is the standards-grounded thread identity/state contract; naruon owns the anti-corruption/projection boundary to LineageWeave.

## Host-visible product gaps

| Gap | Why a host notices | Current maturity |
|---|---|---|
| Public `0.2.0` package | `pip install threadweave` still resolves the older public version until the new protected-main release completes | release candidate on PR #35; public verification pending |
| Incremental mailbox threading | Large changing mailboxes otherwise rebuild the full forest after bounded changes | proposed/active-PR via PR #20; gated behind verified `0.2.0` release |
| Stable RFC 8474 identity handoff | Hosts need replay-safe identity across incremental changes and migrations | active-PR via PR #20; not protected-main/released behavior |
| Orphaned Actions registry records | Governance/control-plane inventory can expose historical active workflow identities after source deletion | detector integrated through PR #32; issue #31 owns authorized cleanup |

## DDD and ownership fitness

ThreadWeave remains a transport-neutral, zero-runtime-dependency threading library. Its domain owns message-reference threading, subject/date ordering policies, protocol projection, and the proposed incremental thread-state aggregate. It does not own mailbox persistence, tenant/auth state, UI, LineageWeave integration, registry-account management, or generic organization release governance.

Generic fleet changelog/tag/GitHub Release governance belongs to `ContextualWisdomLab/.github` under `.github#1552`. ThreadWeave owns its Python package build and PyPI publisher adapter until that product-specific boundary is replaced by an accepted canonical publishing abstraction. Do not duplicate a new generic fleet release engine here.

## Not applicable to this repository

ThreadWeave is a headless Python library with no frontend, UI component, or user-facing visual surface of its own. **Storybook**, Figma, design tokens, and UI/UX accessibility/interaction/animation audits are **Not applicable to this repository**; those belong to host products that render ThreadWeave output.

## Change rule

Update this document in the same PR that opens, closes, releases, re-blocks, or transfers ownership of any row above. Keep it consistent with `docs/TRACEABILITY.md`, `docs/adr/README.md`, and the live issue/PR state. A queued or stale result is not release evidence; a conversation-only policy is not durable until it is captured in the owning code/ADR/workflow.
