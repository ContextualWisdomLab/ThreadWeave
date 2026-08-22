# ThreadWeave Product/Technical Gap Baseline

**Status:** Living document — reconcile on every PR merge, release, or cross-repository dependency change
**Last reviewed:** 2026-08-22

Read this first if you are deciding what to work on next in ThreadWeave. It lists every open PR/issue with its exact blocking dependency, and the one confirmed cross-repository gap (LineageWeave/naruon) so work lands where it actually unblocks something instead of duplicating effort already tracked elsewhere.

## How to use this document

1. Before opening a new PR, check whether the gap you found is already listed below with an owner and blocking dependency.
2. Before merging a PR, update the row it closes so the next contributor does not re-investigate solved gaps.
3. If a gap spans more than one ContextualWisdomLab repository, record both sides here and in the counterpart repository's own gap baseline, and link the exact issue/PR numbers — do not restate the other repository's authority boundary from memory.

## Open PR inventory (2026-08-22)

| PR | Title | State | Blocking dependency | Next action |
|---|---|---|---|---|
| [#20](https://github.com/ContextualWisdomLab/ThreadWeave/pull/20) | `feat: add incremental mailbox threading with stable identity handoff` | Draft, `CONFLICTING` | Issue #17 (external PyPI Trusted Publisher) must close first; the PR body forbids merging before that | Do not rebase/merge yet. Once #17 closes: refresh onto released main, resolve conflicts, rerun full Python 3.10–3.14 + coverage + mailbox-scale parity evidence, get independent review. |
| [#32](https://github.com/ContextualWisdomLab/ThreadWeave/pull/32) | `fix(operations): audit orphaned Actions workflow identities` | Draft, all CI green, `mergeStateStatus: BLOCKED` (review required) | Production module (`scripts/ci/actions_registry_audit.py`) is still the RED-only stub (one docstring line); the design doc at `docs/plans/2026-08-12-actions-registry-audit-design.md` describes the real GREEN implementation, which has not been written yet | Implement the paginated Actions-registry auditor per the committed design doc, add the real classification/evidence tests, then mark ready for review. |

## Open issue inventory (2026-08-22)

| Issue | Title | Blocking dependency | Next action |
|---|---|---|---|
| [#17](https://github.com/ContextualWisdomLab/ThreadWeave/issues/17) | Release operations: complete PyPI Trusted Publishing for 0.2.0 | Repository-owned prerequisite (PR #30) is merged. Remaining blockers are both external and cannot be closed by a source change alone: (a) create a GitHub `pypi` deployment environment with protected-branch-only deployment and an independent required reviewer; (b) configure a PyPI Trusted Publisher on the `threadweave` PyPI project for `ContextualWisdomLab/ThreadWeave`, workflow `release.yml`, environment `pypi`. As of 2026-08-22, `GET /repos/ContextualWisdomLab/ThreadWeave/environments` returns `total_count: 0` and PyPI's public `threadweave` project JSON exposes only `0.1.0`. | A repository admin creates the `pypi` environment and an account owner configures the PyPI Trusted Publisher; do not manually upload a distribution or add a long-lived PyPI token as a substitute (explicit non-bypass rule in the issue). |
| [#31](https://github.com/ContextualWisdomLab/ThreadWeave/issues/31) | `[Fleet incident] Disable orphaned PR 20 repair and hourly-diagnostics workflow identities` | PR #32's real implementation (see above) is the repository-owned detector this issue needs before an authorized operator can safely disable orphan workflow identities | Same as PR #32's next action. |
| [#22](https://github.com/ContextualWisdomLab/ThreadWeave/issues/22) | `[Incident] Hourly Product Development blocks its own GitHub API egress` | Criterion 5 only: needs the PR queue genuinely drained and release policy (issue #17) to permit product development before the bounded OpenCode/NVIDIA path can produce its proof run | Re-check after #17 and the PR queue above both close. |

## Cross-repository gap: LineageWeave evidence consumption (naruon#1437)

**Finding:** ThreadWeave has no PR or issue that mentions LineageWeave — the two products do not connect directly, and per ADR-0009 they never should. The actual dependency chain runs through naruon, ThreadWeave's host:

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

**What this means for ThreadWeave:** nothing changes in ThreadWeave's own scope or runtime surface. ADR-0009 records that boundary explicitly so a future contributor does not add a LineageWeave adapter, HTTP call, or runtime dependency here. The one concrete piece of leverage ThreadWeave contributes to this chain is finishing PR #20 through its existing, already-documented acceptance path (ADR-0004) — that PR is blocked purely by issue #17, not by anything LineageWeave- or naruon-specific.

**What this means for naruon and LineageWeave:** naruon#1437 and LineageWeave#338 are tracked and owned in their own repositories; this document does not restate their acceptance criteria. See naruon#1437 for the full consumer design (admission policy, bounded evidence projection, async durable execution, result projection, buyer surface) and LineageWeave#338 for the provider-side contract.

## Buyer-visible product gaps (independent of the LineageWeave chain)

| Gap | Why a buyer would notice | Current maturity |
|---|---|---|
| Incremental mailbox threading (large-mailbox performance) | A host with a large, actively-changing mailbox must currently rebuild the full thread forest on every arrival/expunge/correction; PR #20 removes that cost but is not yet mergeable | proposed/active-PR (ADR-0004), blocked on issue #17 |
| Published 0.2.0 release | `pip install threadweave` still installs 0.1.0; Python 3.14 support, the documentation graph, and the release-readiness preflight (PR #30) are already on protected main but not yet publicly released | blocked on issue #17 external account-side configuration |
| Orphaned Actions workflow identities | Does not affect library consumers directly, but leaves 27 live workflow identities against 4 supported sources in the organization's automation surface, which is a governance/audit gap for a repository claiming SOC 2/CSAP-aligned practice | PR #32 RED-only; GREEN implementation not yet written |

## Not applicable to this repository

ThreadWeave is a headless, zero-runtime-dependency Python library (see `ARCHITECTURE.md` and `docs/PRD.md`) with no frontend, UI component, or user-facing surface of its own. Storybook, Figma, design tokens, and UI/UX accessibility/interaction/animation audits do not apply here; those belong to host products (e.g., naruon) that render ThreadWeave's output. This document intentionally omits a UI-inventory section rather than fabricating one.

## Change rule

Update this document in the same PR that opens, closes, or re-blocks any row above, and whenever a counterpart repository (naruon, LineageWeave) changes the cross-repository chain's status. Do not let this document drift from `docs/TRACEABILITY.md` and `docs/adr/README.md`; when they disagree, the ADR/traceability maturity label is authoritative and this document must be corrected to match.
