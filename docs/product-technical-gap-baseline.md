# ThreadWeave Product/Technical Gap Baseline

**Status:** Living document — reconcile on every PR merge, release, or cross-repository dependency change
**Last reviewed:** 2026-09-30

Read this first if you are deciding what to work on next in ThreadWeave. It lists every open PR/issue with its exact blocking dependency, and the one confirmed cross-repository gap (LineageWeave/naruon) so work lands where it actually unblocks something instead of duplicating effort already tracked elsewhere.

## How to use this document

1. Before opening a new PR, check whether the gap you found is already listed below with an owner and blocking dependency.
2. Before merging a PR, update the row it closes so the next contributor does not re-investigate solved gaps.
3. If a gap spans more than one ContextualWisdomLab repository, record both sides here and in the counterpart repository's own gap baseline, and link the exact issue/PR numbers — do not restate the other repository's authority boundary from memory.

## Open PR inventory (2026-09-30)

| PR | Title | State | Blocking dependency | Next action |
|---|---|---|---|---|
| [#44](https://github.com/ContextualWisdomLab/ThreadWeave/pull/44) | `fix(ci): restore protected-ref concurrency cancellation` | Ready; exact head `3190776243e545013738fd6a0f30cd9f966d7632`; mergeable | Canonical foundation. Repository-owned CI, SAST, and Security were terminal-success. The earlier CodeQL jobs stopped at an authenticated-verdict wake gap; Noema/Strix failed at review transport rather than a source finding. A 2026-09-30 rerun made Noema GREEN, while CodeQL/Strix were skipped by the then-current central admission path. | Require a fresh authoritative CodeQL/Strix result and current-head independent approval. Local isolated verification on 2026-09-30: Ruff, compileall, doctests, 432 tests, 637/637 statements and 260/260 branches, wheel/sdist build, and `pip check`. Do not merge from the old `CHANGES_REQUESTED` review. |
| [#35](https://github.com/ContextualWisdomLab/ThreadWeave/pull/35) | `fix(release): use approved PyPI token publisher` | Draft; exact head `35ed8f556e1372e123ea81a99316177ffcb06fc6`; mergeable | Issue #17 implementation owner. Its current CI/Security failures inherit the protected-main concurrency defect repaired by #44; CodeQL also has no terminal exact-head verdict. | Keep alive. After #44 integrates, non-force refresh, rerun the complete release/security/package contract, and obtain current-head review before normal merge. |
| [#45](https://github.com/ContextualWisdomLab/ThreadWeave/pull/45) | `docs: make README links registry-safe` | Draft; exact head `f1d0b9999540797cd341a2aa77b75d6694c32cb6`; base `fix/ci-protected-ref-concurrency` | Correctly stacked on #44. CI and SAST passed; dependency-review and CodeQL terminal evidence remain missing. | Preserve the stack. Revalidate only after #44 integrates or the branch deliberately incorporates its final head. |
| [#37](https://github.com/ContextualWisdomLab/ThreadWeave/pull/37) | `docs: make Pages repository navigation durable` | Draft; exact head `714530ee834d0504d3c79879fac845c48d2cb3e8`; base `fix/ci-protected-ref-concurrency` | Correctly stacked on #44. CI and SAST passed; dependency-review and CodeQL terminal evidence remain missing. | Preserve the stack and require fresh exact-head gates after #44. No Pages publication claim is made here. |
| [#48](https://github.com/ContextualWisdomLab/ThreadWeave/pull/48) | `docs(adr): verified APA 7th citations for ADR-0001–0008` | Draft; exact head `0da789d7cbd8e00dfb596f026e20c5b118d9270a`; mergeable | Its five Python jobs fail only because protected `main` lacks #44's concurrency repair. It completely contains #47's valid RFC 5256 citation requirement, but successor carryover is not complete until normal integration. | Keep Draft; after #44, reconcile README/ADR-0008 overlap with #35/#45, rerun checks, and retain #47 until the carryover is verified on protected main. |
| [#47](https://github.com/ContextualWisdomLab/ThreadWeave/pull/47) | `docs(adr): cite RFC 5256 for ADR 0003` | Draft; exact head `eb742e6128cf6196aff3d9e9c08968648456916a`; mergeable | Valid delta is proposed for complete successor carryover by #48. Current CI RED is the protected-main defect repaired by #44, not citation content. | Do not close early. Preserve until #48 carries every locator/citation requirement through normal integration; otherwise repair this branch after #44. |
| [#39](https://github.com/ContextualWisdomLab/ThreadWeave/pull/39) | `refactor(naming): use semantic command helper name` | Draft; exact head `65f4225fe3d97473b61f08d37e432cb2c0197a3b`; mergeable | The 431-pass/1-fail matrix is caused by protected-main concurrency, not the rename; #44 is the prerequisite. | Keep alive. Non-force refresh after #44, then rerun exact-head checks and review. |
| [#43](https://github.com/ContextualWisdomLab/ThreadWeave/pull/43) | `fix(actions): route hourly development through orchestrator free` | Draft; exact head `fe8a9acb2df10ee3a73ac361461c63ee4ef3d01a`; mergeable | Owns issue #38, but remains architecturally incomplete while the leaf workflow owns provider-secret inventory and contextual-orchestrator source/bootstrap instead of a released owner contract. | Keep Draft and fail closed. Complete the immutable contextual-orchestrator release and central reusable caller contract before a thin consumer update; do not copy owner source or use direct-provider fallback. |
| [#46](https://github.com/ContextualWisdomLab/ThreadWeave/pull/46) | `test(ci): remove superseded concurrency assertion` | Draft; exact head `b88de2c8e07a2c2f794710cc475342f30efa1738`; mergeable | Deleting the assertion would weaken #44's repaired contract. #44 carries the valid RCA and GREEN requirement with the correct workflow fix. | Do not merge or close early. Once #44 integrates normally, verify complete successor carryover and only then retire #46 with recorded evidence. |
| [#20](https://github.com/ContextualWisdomLab/ThreadWeave/pull/20) | `feat: add incremental mailbox threading with stable identity handoff` | Draft; exact head `9a62efa8412f8800372bbbd078d6aec2f3afc7b8`; `CONFLICTING` | Issue #17 and the verified 0.2.0 release must close first. | Do not rebase or merge yet. After release: non-force refresh onto released main, resolve conflicts, rerun Python 3.10–3.14, 100% coverage, randomized parity, and 100,000-message evidence, then obtain current-head review. |

### Canonical dependency graph

The shortest safe integration path is `#44 → #35 → issue #17 release proof → #20`.
PRs #45 and #37 are already stacked on #44. PRs #39, #47, and #48 remain
alive behind the same foundation and must be refreshed without force-push after
it lands. PR #46 is not a competing writer: its valid requirement is carried by
#44, while its assertion deletion is deliberately rejected.

## Open issue inventory (2026-09-30)

| Issue | Title | Blocking dependency | Next action |
|---|---|---|---|
| [#17](https://github.com/ContextualWisdomLab/ThreadWeave/issues/17) | Release operations: publish and verify ThreadWeave 0.2.0 | The former external Trusted Publisher prerequisite is superseded. The approved organization `PIPY_TOKEN` publisher path is implemented only on Draft PR #35. | Merge #44, refresh and complete #35, then require protected-main CI, deterministic artifacts, SLSA/SPDX evidence, immutable tag/release, public filename/SHA-256 equality, and clean `threadweave==0.2.0` install/THREAD smoke. Never expose credential values. |
| [#19](https://github.com/ContextualWisdomLab/ThreadWeave/issues/19) | `[Post-0.2.0 Product Gap] Incremental mailbox threading with stable identity handoff` | Implemented on Draft PR #20 but explicitly gated behind issue #17 and the verified 0.2.0 release. | Preserve active-PR maturity. After release, refresh #20 and reacquire parity, hostile-input, concurrency, snapshot, and mailbox-scale evidence. |
| [#38](https://github.com/ContextualWisdomLab/ThreadWeave/issues/38) | Route hourly workflow through `orchestrator/free` | Draft PR #43 removes direct provider routing but still violates the owner boundary by consuming provider secrets and contextual-orchestrator source/bootstrap in the leaf. | Complete the canonical owner release/reusable caller prerequisite, then reduce ThreadWeave to a thin fail-closed consumer and verify model behavior on the exact head. |
| [#31](https://github.com/ContextualWisdomLab/ThreadWeave/issues/31) | `[Fleet incident] Disable orphaned PR 20 repair and hourly-diagnostics workflow identities` | Detection shipped through the earlier PR #32 lineage, but the issue still requires authorized live registry mutation and immutable before/after evidence. | Re-fetch the full registry at the exact protected-main SHA, disable only verified active-orphan identities through the authorized operator path, and retain supported CI/hourly/release workflows. |
| [#22](https://github.com/ContextualWisdomLab/ThreadWeave/issues/22) | `[Incident] Hourly Product Development blocks its own GitHub API egress` | Criteria 1–4 are satisfied. Criterion 5 requires issue #17 closed and the truthful PR queue drained before the bounded model path can execute. | Keep open without manufacturing an empty queue. Record a protected-main bounded proposal/defer run only after the release and queue gates permit it. |

## Cross-repository gap: LineageWeave evidence consumption (naruon#1437)

**Finding:** ThreadWeave has no production-integration PR or issue that mentions LineageWeave — the two products do not connect directly, and ADR-0009 (Proposed) records that they should not connect directly if accepted. The actual dependency chain runs through naruon, ThreadWeave's host:

```text
ContextualWisdomLab/naruon#1437 (Consume LineageWeave for email lineage and
  project intelligence, without duplicating authority)
  → depends on naruon#1350 (canonical email identity, dedupe, thread graph)
    → depends on a stable, replay-safe thread identity that survives
      incremental mailbox changes
      → this is exactly ThreadWeave PR #20 / ADR-0004's
        IncrementalThreadIndex + RFC 8474 EMAILID/THREADID contract
  → also depends on ContextualWisdomLab/LineageWeave#338 (publish the
    provider-side evidence-bounded lineage contract)
```

Relation-level statement (authoritative, mirrors ADR-0009): `naruon#1437`
depends on `naruon#1350`, which depends on ThreadWeave PR #20;
`naruon#1437` also depends on `LineageWeave#338` as a separate branch —
not as a transitive step through `naruon#1350`.

**What this means for ThreadWeave:** nothing changes in ThreadWeave's own scope or runtime surface. ADR-0009 (Proposed) records that boundary explicitly so a future contributor does not add a LineageWeave adapter, HTTP call, or runtime dependency here if the ADR is accepted. The one concrete piece of leverage ThreadWeave contributes to this chain is finishing PR #20 through its existing, already-documented acceptance path (ADR-0004) — that PR is blocked by both its current `CONFLICTING` merge state and issue #17's release gate, not by anything LineageWeave- or naruon-specific.

**What this means for naruon and LineageWeave:** naruon#1437 and LineageWeave#338 are tracked and owned in their own repositories; this document does not restate their acceptance criteria. See naruon#1437 for the full consumer design (admission policy, bounded evidence projection, async durable execution, result projection, consumer-facing surface) and LineageWeave#338 for the provider-side contract.

## Host-visible product gaps (independent of the LineageWeave chain)

| Gap | Why a host would notice | Current maturity |
|---|---|---|
| Incremental mailbox threading (large-mailbox performance) | A host with a large, actively-changing mailbox must currently rebuild the full thread forest on every arrival/expunge/correction; PR #20 removes that cost but is not yet mergeable | proposed/active-PR (ADR-0004), blocked on issue #17 |
| Published 0.2.0 release | `pip install threadweave` still installs 0.1.0; Python 3.14 support and the release-readiness foundation exist, but the reviewed organization-token publication path is only on PR #35 | blocked on #44 → #35 → issue #17 public-artifact proof |
| Orphaned Actions workflow identities | Historical repair workflow records remain a control-plane audit gap even after their source files left protected main | detector lineage implemented; issue #31 remains open for authorized live disablement plus immutable before/after evidence |
| CI protected-ref runner cancellation | `main` push runs currently key concurrency by `github.run_id`, so `cancel-in-progress: true` cannot cancel an older run for the same protected ref. This wastes runner capacity and causes dependent PRs to inherit a contradictory regression. | PR #44 implementation locally GREEN at exact head; pending authoritative hosted CodeQL/Strix evidence, independent approval, and normal merge |
| Governed model route | The hourly development workflow still exposes direct-provider/bootstrap responsibility at the leaf boundary | issue #38 / Draft PR #43; blocked on an immutable contextual-orchestrator owner release and reusable central caller contract |

## Not applicable to this repository

ThreadWeave is a headless, zero-runtime-dependency Python library (see `ARCHITECTURE.md` and `docs/PRD.md`) with no frontend, UI component, or user-facing surface of its own. Storybook, Figma, design tokens, and UI/UX accessibility/interaction/animation audits do not apply here; those belong to host products (e.g., naruon) that render ThreadWeave's output. This document intentionally omits a UI-inventory section rather than fabricating one.

## Change rule

Update this document in the same PR that opens, closes, or re-blocks any row above, and whenever a counterpart repository (naruon, LineageWeave) changes the cross-repository chain's status. Do not let this document drift from `docs/TRACEABILITY.md` and `docs/adr/README.md`; when they disagree, the ADR/traceability maturity label is authoritative and this document must be corrected to match.
