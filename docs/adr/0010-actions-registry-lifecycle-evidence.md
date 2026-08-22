# ADR-0010: Separate Actions registry observation from workflow-disable authority

**Status:** Accepted
**Date:** 2026-08-22
**Implementation:** PR #32, `scripts/ci/actions_registry_audit.py`

## Context

Issue #31 recorded a fleet incident: protected `main` contains four supported GitHub Actions workflow sources, but the live GitHub Actions registry reported 27 workflow identities. Historical PR #20 repair, lock-bootstrap, hourly-diagnosis, and finalizer workflows had their source YAML deleted from the tree, but their independent registry records stayed `state: active`. Deleting a workflow's source file is not complete lifecycle cleanup — GitHub's Actions registry tracks workflow identities separately from the tree, and file deletion alone does not disable them (GitHub, 2026b).

Two unsafe shortcuts were considered and rejected:

1. **Restoring the deleted repair YAML** — this recreates the exact temporary-writer authority that caused the incident.
2. **Disabling by name** — matching on substrings like `apply`, `once`, or `release` is not proof of orphanhood, and risks disabling supported automation that happens to share a naming pattern.

Detection and mutation are also distinct risk surfaces: an auditor that can both observe and disable workflows becomes an attractive target and a single point of failure for the organization's automation surface. ADR-0005 already separates model development, verification, publication, review, merge, and release authority for the same reason.

## Decision

`scripts/ci/actions_registry_audit.py` is a read-only, standard-library-only Python detector. It:

- fetches the complete, paginated GitHub Actions workflow registry and the complete, paginated set of open same-repository pull requests;
- binds every observation to an exact protected-main branch SHA, re-read and compared at the end of the audit so a branch move during the run is detected rather than silently ignored;
- reads the exact Git tree at protected-main and at every open PR head to determine which workflow paths are genuinely present as source;
- classifies every registry record into exactly one of seven finite buckets: `present_active`, `present_disabled`, `active_pr_workflow`, `orphan_active`, `orphan_disabled`, `dynamic_owned`, or `unresolved`;
- emits one deterministic, schema-versioned (`threadweave.actions-registry-audit/v1`) JSON report naming only `orphan_active` records as `recommended_disable_workflow_ids`;
- never calls a disable, delete, or write endpoint.

`.github/workflows/actions-registry-audit.yml` runs this detector with exactly `actions: read`, `contents: read`, and `pull-requests: read` — no `actions: write`, no `pull-requests: write`, and no long-lived or elevated credential. It runs on relevant pull requests, on protected-main changes to the detector itself, on manual dispatch, and hourly at minute 53 (distinct from Hourly PR Maintenance's minute 11 and Hourly Product Development's minute 41, so the three heartbeats never contend for the same runner minute). The workflow uploads its report as evidence even when the audit finds an orphan or fails, then fails the job visibly rather than swallowing the finding.

Disabling a confirmed `orphan_active` workflow identity remains a separate, authorized, out-of-band operator action: re-read the exact live registry, re-run this audit against the current protected-main SHA, and disable only the identities that are still confirmed orphans at that moment, through the GitHub Actions lifecycle API with an explicit mutation credential this detector never holds.

## Consequences

- Every registry record has an auditable, finite explanation instead of an unresolved discrepancy between the tree and the registry.
- The detector can run unattended on an hourly heartbeat and on every relevant PR without expanding the organization's write-capable automation surface.
- Disablement still requires a human or a separately authorized control-plane action to re-verify current state immediately before mutating — this ADR does not grant that authority to anything.
- Coordinate with the central lifecycle tracking issue `ContextualWisdomLab/.github#945` and the AppGuardrail orphan-workflow detector issue `ContextualWisdomLab/appguardrail#929`; this ADR does not supersede either.

## References

GitHub. (2026a). *API versions*. GitHub Docs. https://docs.github.com/en/rest/about-the-rest-api/api-versions

GitHub. (2026b). *REST API endpoints for GitHub Actions workflows*. GitHub Docs. https://docs.github.com/en/rest/actions/workflows
