# ADR-0007: Exact Evidence Identity for Review, Merge, and Release

**Status:** Accepted  
**Date:** 2026-08-10

## Context

GitHub pull requests expose several related but non-identical commit identities: contributor head, PR base snapshot, current live protected-base tip, and synthetic merge commits. Workflow systems may test one while reviewers or branch protection reason about another. Treating them as interchangeable can promote stale or synthetic evidence into an incorrect merge/release decision.

## Decision

ThreadWeave records and reasons about these identities separately:

- **contributor head SHA** — exact commit containing the proposed branch changes;
- **PR base snapshot SHA** — base recorded by the pull request at the observed point;
- **live protected-base tip SHA** — independently refetched current target-branch head;
- **synthetic merge SHA** — GitHub-generated merge result used by some PR workflows;
- **tested checkout SHA/ref** — what a workflow actually materialized and tested.

A check/review is authoritative only for the identity it actually evaluated. A predecessor-head success, stale live-base assessment, queued/skipped/cancelled job, synthetic-only result, or mutable-branch assertion cannot be relabelled as exact-current-head success.

## Merge rule

Before merge or auto-merge activation, refetch:

1. current contributor head SHA;
2. current live protected-base tip;
3. draft/mergeability state;
4. required checks and their tested identity;
5. formal reviews and unresolved review threads;
6. security/release blockers.

If the head or live base changes materially, invalidate stale conclusions and re-evaluate. Whether a base move requires a rerun depends on repository policy and whether the verified merge/integration result remains valid; do not simply copy predecessor evidence forward.

## Release rule

Release evidence must name the exact integrated protected commit used to build artifacts. PR-head or synthetic-merge evidence does not prove a public release artifact unless the release workflow itself is bound to the same integrated commit and verifies the resulting artifacts.

## Documentation rule

PR bodies, audit records, and incident reports should not use a single ambiguous `base SHA` label. Where relevant, name `pr_base_snapshot_sha` and `live_base_tip_sha` separately. Active-PR performance/coverage claims must name the exact contributor head they describe.

## Consequences

### Positive

- stale evidence cannot silently survive branch movement;
- review, CI, and release provenance remain reconstructable;
- central workflows and repository workflows can be compared without assuming they tested the same ref.

### Negative

- automation must perform additional refetches and metadata bookkeeping;
- a green check on a predecessor head may need to be rerun after a meaningful branch/base change.

## Verification

Repository and central automation should maintain regression contracts for exact-head/live-base handling, and reviewers must treat ambiguous evidence as insufficient rather than guessing the intended identity.