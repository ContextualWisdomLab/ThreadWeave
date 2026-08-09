# ADR-0006: Work-Conserving Autonomous Maintenance

**Status:** Accepted  
**Date:** 2026-08-10

## Context

ThreadWeave uses repository and organization automation to review, repair, verify, merge, release, and continue product development. A workflow that stops after reporting a queued review/check, after one merge, or after one documentation change leaves safe executable work unused and causes the repository to drift from its commercial-readiness target.

GitHub review and Actions latency are normal asynchronous item states. They are not repository-wide reasons to stop. At the same time, autonomous work must not bypass branch protection, independent review, security checks, or external authority boundaries.

## Decision

ThreadWeave maintenance is **work-conserving**:

1. begin each invocation from freshly refetched protected-main, open PRs/issues, exact contributor heads, PR base snapshots, independently resolved live base tips, formal reviews, unresolved threads, required checks, security gates, and release blockers;
2. for each actionable PR, perform review inspection → root-cause analysis → test-first repair where behavior changes → focused/full verification → exact-head gate refetch → merge/auto-merge only when policy permits;
3. after any merge, close, head change, or blocker transition, refetch immediately and continue;
4. queued/pending external work blocks only that item; select the next safe executable repository action instead of waiting;
5. when the PR/issue queue is genuinely drained, perform documentation fitness plus buyer-visible/release-readiness gap analysis and open at most one bounded high-value implementation line at a time;
6. before stopping, perform a double exit sweep and stop only when the invocation budget is exhausted or every remaining item is externally blocked/read-only/unsafe.

The hourly recurrence is continuation, not permission to defer work that is executable now.

## Safety constraints

- No required review/check is weakened or bypassed.
- No approval is inferred from status-only, `COMMENTED`, skipped, queued, cancelled, stale, or predecessor-head evidence.
- No one-shot/self-modifying/encoded-patch workflow is created to repair an ordinary branch change.
- The development model cannot merge, release, or manufacture independent approval.
- Repository automation must use bounded concurrency and must not create duplicate PRs for the same product gap.
- Organization-central dependencies or repositories with their own active writer loops are read-only unless a separate authority grants a write lease.

## Model-backed development

Scheduled model-backed product work uses an immutably pinned OpenCode Agent and `NVIDIA_NIM_API_KEY` for the model execution boundary. `COPILOT_GITHUB_TOKEN` is not a development-model credential and must not be introduced into this path. Deterministic verification, publication, independent review, merge, and release authority remain separate.

## Consequences

### Positive

- CI/review queues no longer create idle repository-wide dead time.
- Documentation, operational hardening, and buyer gaps continue while one PR is externally blocked.
- Every action remains tied to current evidence and branch protection.
- The loop naturally converges toward zero actionable PRs/issues and then toward higher product quality.

### Negative

- More state refetches are required.
- The scheduler must avoid duplicate work and cross-repository write collisions.
- Some invocations will end with externally blocked items still open; this is acceptable only after all other safe work is exhausted.

## Verification

Automation and documentation tests should assert the hourly cadence, exact repository ownership, NVIDIA/OpenCode credential boundary, current-head evidence rules, and no-early-stop/double-sweep semantics where these are encoded in repository workflows or agent guidance.