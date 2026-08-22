# Read-only GitHub Actions Registry Lifecycle Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect active GitHub Actions workflow identities that lack exact protected-main or current same-repository PR source without giving the detector mutation authority.

**Architecture:** Add one standard-library Python control-plane auditor with injected API reads, strict identity/pagination/tree/race validation, finite classifications, and atomic bounded JSON evidence. Run it from a read-only hourly/manual workflow and extend canonical governance documentation and exact 100% script coverage.

**Tech Stack:** Python 3.10–3.14 standard library, pytest 9.1.1, coverage.py 7.15.3, GitHub REST API `2026-03-10`, GitHub Actions.

## Global Constraints

- The detector is read-only and receives only `actions: read`, `contents: read`, and `pull-requests: read`.
- No `COPILOT_GITHUB_TOKEN`, PAT, guessed credential, `secrets: inherit`, OIDC, or model credential may be added.
- Never recreate deleted repair workflows or disable a workflow by name alone.
- Exact lowercase 40-hex protected-main and same-repository PR-head identities are mandatory.
- Incomplete pagination, malformed metadata, truncated trees, path ambiguity, or state movement fails closed.
- Production statement and branch coverage and production callable docstrings remain exactly 100% on Python 3.10–3.14.
- GitHub-hosted exact-head checks, review, and protected merge authority remain mandatory.

---

### Task 1: Establish the fail-first product contract

**Files:**
- Create: `tests/test_actions_registry_audit.py`
- Create: `docs/superpowers/specs/2026-08-12-actions-registry-audit-design.md`
- Create: `docs/superpowers/plans/2026-08-12-actions-registry-audit.md`

**Interfaces:**
- Consumes: protected-main repository layout.
- Produces: a RED assertion that `scripts/ci/actions_registry_audit.py` must exist and the accepted design/plan.

- [ ] **Step 1: Write the failing test**

```python
def test_actions_registry_audit_production_module_exists() -> None:
    assert MODULE_PATH.is_file(), "scripts/ci/actions_registry_audit.py is not implemented"
```

- [ ] **Step 2: Run the exact test and observe RED**

Run: `pytest -q tests/test_actions_registry_audit.py`

Expected: one assertion failure naming the absent production module, with successful test collection.

- [ ] **Step 3: Commit only the RED test and reviewed design records**

```bash
git add tests/test_actions_registry_audit.py docs/superpowers/specs docs/superpowers/plans
git commit -m "test(operations): require Actions registry lifecycle audit"
```

### Task 2: Implement strict identities, paths, and finite classifications

**Files:**
- Create: `scripts/ci/actions_registry_audit.py`
- Modify: `tests/test_actions_registry_audit.py`

**Interfaces:**
- Produces: `AuditError`, `normalize_repository`, `normalize_sha`, `normalize_workflow_path`, `classify_workflow_records`.

- [ ] **Step 1: Replace the existence-only test with failing identity and classification tests**
- [ ] **Step 2: Run focused tests and verify failures are caused by missing functions**
- [ ] **Step 3: Implement minimal validation and classification code**
- [ ] **Step 4: Run focused tests and retain 100% statement/branch coverage**
- [ ] **Step 5: Commit the independently reviewable classification boundary**

### Task 3: Implement complete pagination and exact tree authority

**Files:**
- Modify: `scripts/ci/actions_registry_audit.py`
- Modify: `tests/test_actions_registry_audit.py`

**Interfaces:**
- Produces: `list_workflow_records`, `list_open_pull_requests`, `workflow_paths_from_tree`, `same_repository_pr_snapshot`, `protected_workflow_paths`.

- [ ] **Step 1: Add RED tests for page receipts, repeated pages, total-count mismatch, caps, malformed pages, tree truncation, fork exclusion, and malformed current-head identity**
- [ ] **Step 2: Run focused tests and verify the intended failures**
- [ ] **Step 3: Implement bounded complete reads and exact tree extraction**
- [ ] **Step 4: Run focused coverage and make every production branch observable**
- [ ] **Step 5: Commit the complete-inventory boundary**

### Task 4: Implement final revalidation and bounded evidence

**Files:**
- Modify: `scripts/ci/actions_registry_audit.py`
- Modify: `tests/test_actions_registry_audit.py`

**Interfaces:**
- Produces: `audit_actions_registry`, `encode_report`, `write_report_atomically`.

- [ ] **Step 1: Add RED tests for main movement, registry drift, PR-head drift, collisions, confirmed disable IDs, deterministic ordering, byte limits, and atomic output**
- [ ] **Step 2: Run tests and verify the expected failures**
- [ ] **Step 3: Implement the final race boundary and schema-v1 evidence**
- [ ] **Step 4: Run exact focused coverage at 100%**
- [ ] **Step 5: Commit the evidence boundary**

### Task 5: Implement strict GitHub HTTP and CLI behavior

**Files:**
- Modify: `scripts/ci/actions_registry_audit.py`
- Modify: `tests/test_actions_registry_audit.py`

**Interfaces:**
- Produces: `GitHubJsonClient`, `main(argv=None)`.

- [ ] **Step 1: Add RED tests for strict UTF-8, duplicate JSON keys, status errors, missing token, response bounds, redacted diagnostics, CLI conclusions, and report preservation on findings**
- [ ] **Step 2: Run focused tests and verify production behavior is missing**
- [ ] **Step 3: Implement the standard-library HTTP client and CLI**
- [ ] **Step 4: Run focused statement/branch coverage and compilation**
- [ ] **Step 5: Commit the executable detector**

### Task 6: Add the least-authority workflow and permanent CI gate

**Files:**
- Create: `.github/workflows/actions-registry-audit.yml`
- Create: `tests/test_actions_registry_audit_workflow.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Consumes: `python scripts/ci/actions_registry_audit.py audit ...`.
- Produces: hourly/manual exact-main report artifact and pull-request contract coverage.

- [ ] **Step 1: Add RED source-contract tests for triggers, permissions, concurrency, pinned actions, Python 3.14, exact-head checkout, always-upload evidence, final visible failure, and absence of write authority**
- [ ] **Step 2: Run tests and verify the workflow is absent**
- [ ] **Step 3: Add the workflow and extend `ci.yml` focused script coverage to the new module/tests**
- [ ] **Step 4: Run action/source contracts, focused coverage, compileall, and `git diff --check`**
- [ ] **Step 5: Commit the workflow and permanent quality gate**

### Task 7: Integrate the canonical governance record

**Files:**
- Create: `docs/adr/0010-actions-registry-lifecycle-evidence.md`
- Modify: `docs/adr/README.md`
- Modify: `docs/OPERABILITY.md`
- Modify: `docs/INCIDENT_RUNBOOK.md`
- Modify: `docs/TEST_STRATEGY.md`
- Modify: `docs/THREAT_MODEL.md`
- Modify: `docs/TRACEABILITY.md`
- Modify: `DOCUMENTATION.md`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_architecture_documentation.py`

**Interfaces:**
- Produces: accepted observation/mutation separation and explicit post-merge operator acceptance.

- [ ] **Step 1: Add RED documentation contracts requiring ADR-0010, issue #31 traceability, central `.github#945`, AppGuardrail #929, and protected-main/post-disable evidence separation**
- [ ] **Step 2: Run documentation tests and observe intended failures**
- [ ] **Step 3: Add and index the canonical records with APA 7th primary-source citations**
- [ ] **Step 4: Run documentation, complete repository, docstring, package, and exact coverage gates**
- [ ] **Step 5: Commit canonical documentation integration**

### Task 8: Publish and revalidate the Draft PR

**Files:**
- Modify: pull-request body and review state only.

**Interfaces:**
- Produces: exact-head hosted evidence; no merge or workflow disablement without live authority.

- [ ] **Step 1: Push the non-forced branch and update the Draft PR with exact head/base identities and RED/GREEN lineage**
- [ ] **Step 2: Inspect every exact-head application, security, supply-chain, and semantic-review result**
- [ ] **Step 3: Address each valid finding test-first and resolve only repaired threads**
- [ ] **Step 4: Keep Draft while any exact-head gate, independent review requirement, or operational disablement evidence is incomplete**
- [ ] **Step 5: After protected integration, run the live audit, disable only revalidated confirmed orphan IDs through an authorized separate action, and retain before/after proof before closing #31**
