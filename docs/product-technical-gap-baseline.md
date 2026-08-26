# ThreadWeave Product/Technical Gap Baseline

**Status:** Living document — reconcile on every PR merge, release, or cross-repository dependency change
**Last reviewed:** 2026-08-23

Read this first if you are deciding what to work on next in ThreadWeave. It lists every open PR/issue with its exact blocking dependency, and the one confirmed cross-repository gap (LineageWeave/naruon) so work lands where it actually unblocks something instead of duplicating effort already tracked elsewhere.

## How to use this document

1. Before opening a new PR, check whether the gap you found is already listed below with an owner and blocking dependency.
2. Before merging a PR, update the row it closes so the next contributor does not re-investigate solved gaps.
3. If a gap spans more than one ContextualWisdomLab repository, record both sides here and in the counterpart repository's own gap baseline, and link the exact issue/PR numbers — do not restate the other repository's authority boundary from memory.

## Open PR inventory (2026-08-23)

| PR | Title | State | Blocking dependency | Next action |
|---|---|---|---|---|
| [#20](https://github.com/ContextualWisdomLab/ThreadWeave/pull/20) | `feat: add incremental mailbox threading with stable identity handoff` | Draft, `CONFLICTING` | Issue #17 (external PyPI Trusted Publisher) must close first; the PR body forbids merging before that | Do not rebase/merge yet. Once #17 closes: refresh onto released main, resolve conflicts, rerun full Python 3.10–3.14 + coverage + mailbox-scale parity evidence, get independent review. |
| [#32](https://github.com/ContextualWisdomLab/ThreadWeave/pull/32) | `fix(operations): audit orphaned Actions workflow identities` | Open (marked ready for review), all required checks green, no unresolved review threads | Production module (`scripts/ci/actions_registry_audit.py`) is fully implemented and has been through several review rounds (CodeRabbit/Devin/github-code-quality) with every finding fixed or explicitly addressed: identity/path validation, complete verified pagination, protected-main/PR-head tree reads, the seven-way finite classification model, atomic schema-v1 evidence, a strict `GitHubJsonClient`, and `.github/workflows/actions-registry-audit.yml` at exactly `actions: read`/`contents: read`/`pull-requests: read`. 100% statement/branch/docstring coverage. Will be recorded as **ADR-0010** once PR #32 merges; the ADR file is not yet on this branch. | Historically blocked by two org-level conditions, both now cleared on protected `.github` main: `.github#624` (provider outage) and the strix provider-routing defect fixed via `.github` PR #1322 (superseding #1213). No repository-side action remains; merge gates now evaluate normally. |
| [#34](https://github.com/ContextualWisdomLab/ThreadWeave/pull/34) | `docs: add product/technical gap baseline and LineageWeave consumer boundary ADR` | Open, all required checks green, no unresolved review threads (this document's own PR) | Same dual blocker as #32 (`.github#624` + strix routing fixed by `.github` PR #1322 superseding #1213) — both cleared; this PR is merging through normal gates. |

### Correction to the "`#624` blocks everything" reading (2026-08-23)

`.github#624` is real but is no longer the whole story, and treating it as the
single blocker sends the next contributor to the wrong repository. Two further,
independently-reproduced root causes now sit between these PRs and a merge:

1. **`strix` provider-routing defect (org-wide, in `.github` `main`).**
   `STRIX_FALLBACK_MODELS` ends in the hyphenated `openai-direct/gpt-5.6-luna`
   alias — a spelling protected main's own trusted
   `scripts/ci/strix_required_workflow_smoke.sh` pins verbatim, so the value
   cannot be changed. `scripts/ci/strix_quick_gate.sh` recognized only the
   underscored `openai_direct/` form, so once NVIDIA NIM rate-limited the
   primary and first fallback model, the third fallback reached LiteLLM as a
   literal unrecognized provider string and the scan died with
   `litellm.BadRequestError: LLM Provider NOT provided`. Reproduced three times
   deterministically; the same signature is failing LineageWeave's own required
   `strix` check. Fix in flight as `.github#1213`.
2. **`pull_request_target` self-reference trap.** `strix.yml` resolves its
   trusted source via `job.workflow_sha`, which on `pull_request_target`
   resolves to the **base branch** commit. Every `.github` PR's own `strix`
   check therefore fetches `strix_quick_gate.sh` from protected `main`,
   regardless of the PR branch's contents. A PR that fixes that file cannot
   verify its own fix; only a merge to `main` can. This is why the standalone
   fix attempt (`.github#1256`) was correctly closed as superseded rather than
   iterated on.

**What this means for ThreadWeave (2026-08-25 update):** no repository-side action was ever required for PR #32 or PR #34. Both org-level blockers have now cleared — provider access is restored past `.github#624`, and the strix provider-routing defect is fixed on protected `.github` main by PR #1322 (which supersedes #1213). Both PRs proceed through their normal merge gates.

## Open issue inventory (2026-08-23)

| Issue | Title | Blocking dependency | Next action |
|---|---|---|---|
| [#17](https://github.com/ContextualWisdomLab/ThreadWeave/issues/17) | Release operations: complete PyPI Trusted Publishing for 0.2.0 | Repository-owned prerequisite (PR #30) is merged. Remaining blockers are both external and cannot be closed by a source change alone: (a) create a GitHub `pypi` deployment environment with protected-branch-only deployment and an independent required reviewer; (b) configure a PyPI Trusted Publisher on the `threadweave` PyPI project for `ContextualWisdomLab/ThreadWeave`, workflow `release.yml`, environment `pypi`. As of 2026-08-23, `GET /repos/ContextualWisdomLab/ThreadWeave/environments` returns `total_count: 0` and PyPI's public `threadweave` project JSON exposes only `0.1.0`. | A repository admin creates the `pypi` environment and an account owner configures the PyPI Trusted Publisher; do not manually upload a distribution or add a long-lived PyPI token as a substitute (explicit non-bypass rule in the issue). |
| [#31](https://github.com/ContextualWisdomLab/ThreadWeave/issues/31) | `[Fleet incident] Disable orphaned PR 20 repair and hourly-diagnostics workflow identities` | PR #32's real implementation (see above) is the repository-owned detector this issue needs before an authorized operator can safely disable orphan workflow identities | Unblocked with PR #32: both org-level blockers (`.github#624`; strix routing, fixed by `.github` PR #1322 superseding #1213) are cleared, so the detector can be operated against live workflow identities. |
| [#22](https://github.com/ContextualWisdomLab/ThreadWeave/issues/22) | `[Incident] Hourly Product Development blocks its own GitHub API egress` | Criterion 5 only: needs the PR queue genuinely drained and release policy (issue #17) to permit product development before the bounded OpenCode/NVIDIA path can produce its proof run | Re-check after #17 and the PR queue above both close. The queue (#32, #34) isn't stuck on scheduling — it's the same `.github#624` review-dispatch outage. |

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
| Published 0.2.0 release | `pip install threadweave` still installs 0.1.0; Python 3.14 support, the documentation graph, and the release-readiness preflight (PR #30) are already on protected main but not yet publicly released | blocked on issue #17 external account-side configuration |
| Orphaned Actions workflow identities | Does not affect library consumers directly, but leaves 27 live workflow identities against 4 supported sources in the organization's automation surface, which is a governance/audit gap for a repository claiming SOC 2/CSAP-aligned practice | PR #32 GREEN implementation complete (to be recorded as ADR-0010 after merge); pending CI/review/merge |

## Not applicable to this repository

ThreadWeave is a headless, zero-runtime-dependency Python library (see `ARCHITECTURE.md` and `docs/PRD.md`) with no frontend, UI component, or user-facing surface of its own. Storybook, Figma, design tokens, and UI/UX accessibility/interaction/animation audits do not apply here; those belong to host products (e.g., naruon) that render ThreadWeave's output. This document intentionally omits a UI-inventory section rather than fabricating one.

## Change rule

Update this document in the same PR that opens, closes, or re-blocks any row above, and whenever a counterpart repository (naruon, LineageWeave) changes the cross-repository chain's status. Do not let this document drift from `docs/TRACEABILITY.md` and `docs/adr/README.md`; when they disagree, the ADR/traceability maturity label is authoritative and this document must be corrected to match.
