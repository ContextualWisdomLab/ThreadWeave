# Hourly autonomous maintenance

**Audience:** repository maintainers and automation operators.  
**Status:** Accepted repository-operations procedure.  
**Last reviewed:** 2026-08-16

This is the internal playbook for ThreadWeave's scheduled review, verification,
and model-backed product-development workflows. Customers and host integrators
should use [`README.md`](../../README.md) and [`docs/OPERABILITY.md`](../OPERABILITY.md).
Decision records remain [`ADR-0005`](../adr/0005-automation-authority-separation.md)
and [`ADR-0006`](../adr/0006-work-conserving-autonomous-maintenance.md).

Three staggered workflows keep development review-first and single-flight.

At minute 11 of every hour, `hourly-pr-maintenance.yml` calls the organization
workflows in `ContextualWisdomLab/.github` to inspect reviews, dispatch bounded
fixes, revalidate the exact head, update branches, and merge only when policy is
satisfied.

At minute 41, `hourly-product-development.yml` runs only when the PR queue is
empty. Its trust boundary is deliberately split across fresh GitHub-hosted jobs:

1. A runner-local broker owns `NVIDIA_NIM_API_KEY`, injects it only into HTTPS
   requests to the fixed NVIDIA NIM host, strips caller authorization, bounds
   request/response sizes, and suppresses prompt logging. OpenCode receives only
   a non-secret placeholder key and can reach the broker on IPv4 loopback.
2. The model runs as UID 65532 in a disposable, `.git`-free workspace with an
   empty environment, bounded processes and file descriptors, no GitHub or OIDC
   credential, and no publication filesystem. Undeclared network egress is
   blocked; OpenCode web-fetch, web-search, external-directory, task, and LSP
   capabilities are denied. Surviving model descendants are killed before any
   trusted inspection occurs.
3. `scripts/ci/hourly_product_guard.py` accepts only bounded UTF-8 text changes
   under `src/threadweave/`, `tests/`, `docs/`, `README.md`, and `CHANGELOG.md`.
   Workflow, policy, dependency, release, deletion, rename, link, binary,
   executable, mode, size, line-budget, unsafe metadata, and credential-leak
   changes fail closed.
4. Only the sealed patch, SHA-256 digest, exact path inventory, and sanitized PR
   metadata cross the job boundary. A fresh credential-free job reapplies that
   exact patch and independently runs Ruff, compileall, doctests, the full
   pytest/coverage suite, package build, dependency checks, and installed-wheel
   smoke verification.
5. A third fresh publisher starts from `main`, repeats the zero-PR, unchanged-base,
   digest, path, and patch checks, and opens one PR. The model never shares a
   process, filesystem, Git hook, network credential, or GitHub credential with
   publication.

Configure these organization or repository secrets:

- `NVIDIA_NIM_API_KEY`: scoped and rotatable credential held only by the local
  broker and the trusted post-model credential-leak scanner.
- `PR_REVIEW_MERGE_TOKEN` or `OPENCODE_APPROVE_TOKEN`: fine-grained PAT or GitHub
  App token used only by the fresh publisher job.

The external automation token is intentional. GitHub documents that a pull
request created with the repository `GITHUB_TOKEN` leaves its workflow runs
awaiting approval; a GitHub App token or personal access token lets the required
PR workflows start without that manual gate. The product-development agent never
merges, tags, or publishes a release. Do not merge a product-development PR from
the model job or treat a successful model run as merge evidence.

At minute 53, `actions-registry-audit.yml` runs the read-only Actions registry
lifecycle audit (`scripts/ci/actions_registry_audit.py`, [`ADR-0010`](../adr/0010-actions-registry-lifecycle-evidence.md)).
It holds only `actions: read`, `contents: read`, and `pull-requests: read` —
never `actions: write` — and reports which live registry identities are backed
by protected-main source, a current open-PR head, disabled, GitHub-owned/dynamic,
a confirmed orphan, or unresolved. It never disables a workflow itself; disabling
a confirmed orphan remains a separate, authorized, out-of-band operator action.

All three workflows expose a manual `dry_run` or `workflow_dispatch` entry
point. Missing credentials, an open PR, a moved base, a changed patch digest,
failed independent verification, or an unavailable safe proposal stops the
review/development cycle without mutation.

The autonomous patch guard and provider-secret fingerprint guard require
**100%** statement and branch coverage. Model selection and provider fallback
belong to the exact-pinned contextual-orchestrator gateway; this repository does
not maintain another provider proxy. `COPILOT_GITHUB_TOKEN` is not a
development-model credential and must not be introduced into this path.
