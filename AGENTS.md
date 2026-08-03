# AGENTS.md — threadweave

Operating guide for automated agents working on this repository.

`threadweave` is a standards-grounded implementation of the JWZ container model
and RFC 5256 `REFERENCES` threading semantics. Its value is *correctness* — mail
clients and ingestion systems rely on threading being deterministic, tolerant of
historical headers, and incapable of hanging. Treat every change to
`threading.py`, `headers.py`, `subject.py`, and `container.py` as
behaviour-sensitive.

## Invariants that must not regress

1. **Loop-safety.** No input may cause an infinite loop or crash. Self-links,
   mutual references, malformed parent pointers, and cyclic child lists must
   terminate. Before linking A as a parent of B, check that A is not already a
   descendant of B.
2. **Reference authority.** A presumed link created while walking another
   message's `References` chain never steals a container that already has a
   parent. The message's own final effective reference is the only authority
   allowed to replace that presumed parent, and never when replacement creates a
   loop.
3. **RFC 5256 fallback.** Use a valid `References` chain in full. When it is
   absent or contains no valid IDs, use only the first valid `In-Reply-To`
   identifier as the message's parent.
4. **Empty-container pruning.** Remove empty childless containers and
   splice-promote the children of other empty containers. At the root level,
   retain an empty container with multiple children as the grouping root, but
   promote its only child when it has exactly one.
5. **RFC 5256 subject semantics.** Use the exact base-subject procedure,
   including mailing-list blobs, reply/forward leaders, `(fwd)` trailers, and
   `[fwd: ...]` wrappers. During root gathering, retain a dummy container as
   subject-table owner whenever one exists; otherwise prefer a non-reply
   concrete owner over a reply/forward owner.
6. **Missing roots become placeholders.** A referenced-but-unseen `Message-ID`
   yields an empty container that still co-threads its descendants.
7. **Duplicate Message-IDs survive.** A second distinct message with an already
   occupied ID gets its own container; no message may be discarded
   destructively.
8. **Identity semantics.** `Container` objects are mutable graph nodes and
   compare by identity, not recursively by field value.
9. **Determinism.** Root order follows first container creation; sibling and
   descendant traversal follows insertion order. Keep `container_order` and the
   reverse-push iterative depth-first traversal unless tests prove a deliberate
   contract change.
10. **One-shot ingestion.** `thread_messages` and `thread_email_messages` consume
    arbitrary iterables once. Do not require sequence indexing or a second pass
    over caller input.

## Maintenance notes

- Keep the runtime dependency-free; use only the Python standard library.
- The header primitives in `headers.py` originated in naruon. Port compatible
  fixes in both directions or document any intentional divergence.
- Work test-first. Observe the regression fail for the intended reason before
  changing production code.
- Maintain 100% production statement and branch coverage and complete authored
  production docstrings.
- Update `CHANGELOG.md`, public API documentation, and research grounding when a
  change affects behavior or standards claims.
- Keep the package usable both as a standalone distribution and as a naruon
  module/submodule. Avoid repository-specific coupling in the runtime core.

## Autonomous maintenance loop

Two default-branch workflows keep the repository moving without bypassing review:

- `.github/workflows/hourly-pr-maintenance.yml` runs at minute 11 of every UTC
  hour. It delegates review-feedback repair, check revalidation, branch updates,
  and direct/auto merge decisions to the canonical reusable workflows in
  `ContextualWisdomLab/.github`.
- `.github/workflows/hourly-product-development.yml` runs at minute 41. It
  creates one bounded Copilot cloud-agent task only when no pull request and no
  active task (`queued`, `in_progress`, `idle`, or `waiting_for_user`) exists.

The agent-tasks REST API does **not** accept the built-in Actions installation
token. Configure a fine-grained user token with repository **Agent tasks:
read/write** permission as `COPILOT_AGENT_TOKEN` (preferred) or
`COPILOT_GITHUB_TOKEN`. Existing `PR_REVIEW_MERGE_TOKEN` or
`OPENCODE_APPROVE_TOKEN` secrets are tried only as compatibility fallbacks and
must carry the same Agent tasks permission. Missing tokens and task-inventory
failures stop dispatch safely.

Both workflows support `workflow_dispatch` with `dry_run: true`. Scheduled
workflows execute only from the default branch. Do not weaken the pull-request-
first or active-task gates, grant the development task direct merge authority,
or move product dispatch ahead of PR maintenance.

## Verify

```bash
python -m pip install -e ".[test]" ruff coverage build
ruff check .
python -m compileall -q src tests
python -m doctest src/threadweave/headers.py src/threadweave/subject.py
coverage run -m pytest -q
coverage report --fail-under=100
python -m build
python -m pip check
```
