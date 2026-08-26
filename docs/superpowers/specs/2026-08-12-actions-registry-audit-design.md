# Read-only GitHub Actions Registry Lifecycle Audit Design

**Status:** Accepted implementation design for ThreadWeave issue #31  
**Date:** 2026-08-12  
**Protected-main baseline:** `2559425084389176870eac9d1a855d219bc12ce3`

## Problem

ThreadWeave's protected `main` contains four supported workflow sources, while the live GitHub Actions registry reports 27 workflow identities. Historical PR #20 repair, lock-bootstrap, diagnosis, and finalizer paths are absent from the exact protected tree but remain `state: active`. Deleting YAML therefore did not complete the control-plane lifecycle.

The repository needs durable evidence that answers which registry identities are backed by exact protected-main source, temporarily owned by a current same-repository pull-request head, disabled, GitHub-owned/dynamic, confirmed active orphans, or unresolved. Detection must not itself receive workflow-disable authority.

## Chosen approach

Implement a standard-library-only Python auditor plus a read-only scheduled workflow. The auditor consumes GitHub REST metadata through a narrow JSON client, binds observations to an exact protected-main SHA and exact open-PR head snapshot, performs complete pagination, and emits one deterministic bounded JSON report. A separate authorized operator or central control-plane path may use the report only after revalidation to disable confirmed orphan IDs.

This approach is preferred over:

1. **Restoring deleted cleanup YAML.** Rejected because it recreates the same temporary-writer authority that caused the incident.
2. **Name-based disabling.** Rejected because `apply`, `once`, or `release` wording is not proof of orphanhood and could disable supported automation.
3. **Giving the detector `actions: write`.** Rejected because observation and mutation must remain distinct authority planes.

## Classification model

Each registry record receives exactly one finite classification:

- `present_active`: active repository-path identity backed by exact protected-main source;
- `present_disabled`: disabled repository-path identity backed by exact protected-main source;
- `active_pr_workflow`: active path absent from protected main but present on an exact current same-repository open-PR head;
- `orphan_active`: active repository-path identity absent from protected main and every exact current same-repository open-PR head;
- `orphan_disabled`: disabled repository-path identity absent from protected main and current same-repository PR heads;
- `dynamic_owned`: non-repository-path identity managed outside repository YAML authority;
- `unresolved`: malformed, conflicting, ambiguous, incomplete, or race-invalid evidence.

Only positive `orphan_active` records with unique positive integer workflow IDs appear in `recommended_disable_workflow_ids`. The detector never sends the disable request.

## Identity and race boundaries

The audit validates:

- repository identity as canonical `owner/name` text;
- source revision and PR heads as exact lowercase 40-hex SHAs;
- workflow IDs as positive integers excluding booleans;
- repository workflow paths as exact NFC POSIX `.github/workflows/*.yml|yaml` paths with no controls, backslashes, duplicate separators, dot segments, case folding, or percent ambiguity;
- complete workflow and pull-request pagination with page receipts, a finite page cap, `total_count` agreement, and repeated-page rejection;
- non-truncated exact Git trees;
- same-repository PR ownership only;
- unique workflow IDs and unambiguous active canonical paths;
- unchanged default-branch SHA, workflow inventory identity, and open-PR head snapshot at the final revalidation boundary.

A 403, 404, 409, 422, 429, or 5xx; malformed JSON; duplicate JSON key; invalid UTF-8; response-size overflow; pagination mismatch; branch movement; PR-head movement; or workflow inventory drift fails closed. It is not represented as a clean result.

## Report contract

Schema identifier: `threadweave.actions-registry-audit/v1`.

The report contains only bounded control-plane metadata:

- repository;
- exact protected-main SHA;
- UTC observation timestamp;
- GitHub API version;
- workflow and PR pagination receipts;
- exact open-PR same-repository head snapshot;
- finite classifications containing workflow ID, name, normalized path, state, classification, and controlled reason;
- confirmed orphan and unresolved records;
- recommended disable IDs;
- summary counts.

It excludes tokens, headers, raw response bodies, comments, PR titles, model output, repository file contents, and uncontrolled exception text.

## Runtime and workflow

`actions_registry_audit.py` exposes pure validation, pagination, classification, and audit functions plus a CLI. The CLI uses `urllib.request`, strict UTF-8, duplicate-key-rejecting JSON, bounded response reads, the official GitHub API version `2026-03-10`, and atomic report publication.

`.github/workflows/actions-registry-audit.yml` runs:

- on protected-main changes to the detector;
- manually;
- hourly at minute 53, separate from ThreadWeave's minute-11 PR maintenance and minute-41 product loop.

It deliberately does **not** run on `pull_request`: the audit is meant to fail visibly on a genuine live orphan, and while any real orphan remains undisabled that would make it a permanently red check on every unrelated PR. `tests/test_actions_registry_audit.py`, exercised at exact 100% coverage in `ci.yml` on every PR that touches the detector, is the PR-time contract verification for the detector's own correctness.

Permissions are exactly `actions: read`, `contents: read`, and `pull-requests: read`. The live job uploads evidence even when the audit detects an orphan or unresolved state, then fails visibly. It has no contents, pull-request, issue, environment, OIDC, model, secret, release, or Actions write authority.

## Test strategy

Tests use injected deterministic fetch functions and local byte responses. They cover:

- all finite classifications;
- path Unicode/case/control/traversal ambiguity;
- positive identifier and SHA validation;
- duplicate IDs and path collisions;
- complete pagination, `total_count`, page caps, repeated pages, and malformed pages;
- protected-main and active-PR tree truncation;
- fork PR exclusion and malformed same-repository heads;
- active-PR workflow ownership;
- final branch, workflow, and PR snapshot races;
- strict JSON/UTF-8/byte-bound HTTP behavior;
- stable redacted diagnostics and atomic report output;
- workflow permissions, schedule, exact-head checkout, pinned actions, always-upload evidence, and no mutation authority;
- exact 100% statement and branch coverage for the production auditor on Python 3.10–3.14.

## Documentation and operational handoff

ADR-0010 records the durable separation between source deletion, registry state, observation, and disable authority. Operability, incident response, threat model, test strategy, traceability, documentation map, and CHANGELOG link the detector to ThreadWeave #31, central `.github#945`, and AppGuardrail #929.

Protected-main integration is not incident closure. After integration, an authorized operator must re-read the exact report, revalidate the default branch and registry records, disable only confirmed `orphan_active` IDs through the GitHub Actions lifecycle API, preserve all four supported ThreadWeave workflows, and retain before/after evidence.

## Primary sources — APA 7th

GitHub. (2026). *API versions*. GitHub Docs. https://docs.github.com/en/rest/about-the-rest-api/api-versions

GitHub. (2026). *REST API endpoints for Git trees*. GitHub Docs. https://docs.github.com/en/rest/git/trees

GitHub. (2026). *REST API endpoints for workflows*. GitHub Docs. https://docs.github.com/en/rest/actions/workflows
