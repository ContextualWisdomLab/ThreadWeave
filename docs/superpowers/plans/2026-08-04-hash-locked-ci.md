# Hash-Locked CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every network-backed Python tooling installation reproducible from one universal SHA-256-locked requirements file.

**Architecture:** Exact direct pins live in `requirements/ci.in` and corresponding package metadata. A pinned uv compiler deterministically generates `requirements/ci.lock`; CI regenerates and compares it, while test, package, and autonomous-verification jobs install it with pip `--require-hashes`. Build isolation is disabled because the reviewed Hatchling backend is already installed.

**Tech Stack:** Python 3.10-3.13, pip hash-checking mode, uv 0.11.29, Hatchling 1.31.0, GitHub Actions.

## Global Constraints

- Preserve zero runtime dependencies.
- Preserve Python 3.10-3.13 support.
- Preserve 100% production statement and branch coverage.
- Preserve 100% autonomous-boundary statement and branch coverage.
- Do not expose GitHub, OIDC, or model-provider credentials to the autonomous model process.
- Pin every GitHub Action by full commit SHA.
- Update `CHANGELOG.md`, README, AGENTS, and supply-chain documentation.

---

### Task 1: Define the reviewed dependency intent

**Files:**
- Create: `requirements/ci.in`
- Modify: `pyproject.toml`
- Test: `tests/test_dependency_lock_contract.py`

**Interfaces:**
- Consumes: Python project metadata and the existing CI toolchain.
- Produces: exact direct pins shared by package metadata and lock generation.

- [ ] **Step 1: Write failing synchronization tests**

Require exact Hatchling, coverage, pytest, build, and Ruff pins; require no runtime dependency; reject range or wildcard pins.

- [ ] **Step 2: Run the focused test and observe failure**

Run: `pytest -q tests/test_dependency_lock_contract.py`
Expected: FAIL because `requirements/ci.in` and exact metadata pins do not exist.

- [ ] **Step 3: Add exact direct pins**

Create `requirements/ci.in` with the five approved packages and update `pyproject.toml` to exact Hatchling, coverage, and pytest versions.

- [ ] **Step 4: Re-run the focused test**

Run: `pytest -q tests/test_dependency_lock_contract.py`
Expected: PASS.

### Task 2: Add deterministic lock compilation

**Files:**
- Create: `scripts/ci/compile_ci_lock.sh`
- Create: `requirements/ci.lock`
- Modify: `tests/test_dependency_lock_contract.py`

**Interfaces:**
- Consumes: `requirements/ci.in`, uv 0.11.29, cutoff `2026-08-04T00:00:00Z`.
- Produces: a universal pip requirements lock with complete SHA-256 hashes.

- [ ] **Step 1: Add failing compiler-contract tests**

Require `--universal`, `--python-version 3.10`, `--generate-hashes`, fixed `--exclude-newer`, no path-dependent header, and an optional output path.

- [ ] **Step 2: Run the focused test and observe failure**

Run: `pytest -q tests/test_dependency_lock_contract.py`
Expected: FAIL because the compiler script and lock are absent.

- [ ] **Step 3: Implement the compiler and generate the lock**

Use pinned uv 0.11.29 to compile all transitive dependencies and hashes. Generate on a trusted GitHub-hosted runner, not in the model process.

- [ ] **Step 4: Validate the generated lock**

Run: `python -m pip install --require-hashes -r requirements/ci.lock`
Expected: successful installation with no unhashed dependency.

### Task 3: Convert repository CI to the lock

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Consumes: `requirements/ci.lock` and `scripts/ci/compile_ci_lock.sh`.
- Produces: lock-integrity, Python matrix, package, and installed-wheel verification jobs.

- [ ] **Step 1: Add failing workflow tests**

Require a full-SHA setup-uv action, uv 0.11.29, exact lock regeneration, `--require-hashes` installs, no pip upgrades or editable network installs, `--no-isolation` builds, and a hashed local-wheel install.

- [ ] **Step 2: Run workflow tests and observe failure**

Run: `pytest -q tests/test_workflows.py`
Expected: FAIL on the old pip commands.

- [ ] **Step 3: Replace CI install/build commands**

Add lock integrity, set `PYTHONPATH=src`, install only the lock, build without isolation, and smoke-install the local wheel from a temporary hash-bearing requirement.

- [ ] **Step 4: Run workflow and full repository tests**

Run: `pytest -q`
Expected: PASS with production and autonomous-boundary coverage at 100%.

### Task 4: Convert autonomous verification to the lock

**Files:**
- Modify: `.github/workflows/hourly-product-development.yml`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Consumes: the reviewed lock and preinstalled build/test tools.
- Produces: model and reverify environments that cannot resolve unreviewed Python packages.

- [ ] **Step 1: Add failing autonomous-workflow tests**

Reject pip upgrade, editable install, unisolated index access, and isolated build dependency resolution.

- [ ] **Step 2: Run focused tests and observe failure**

Run: `pytest -q tests/test_workflows.py`
Expected: FAIL on existing autonomous pip commands.

- [ ] **Step 3: Use the lock in model and reverify jobs**

Install with `--require-hashes`; retain `PIP_NO_INDEX=1` in the model process; build with `--no-isolation`; hash-install the built wheel.

- [ ] **Step 4: Re-run focused and full tests**

Run: `pytest -q tests/test_workflows.py && pytest -q`
Expected: PASS.

### Task 5: Document provenance and close the issue

**Files:**
- Create: `docs/supply-chain.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CHANGELOG.md`
- Test: `tests/test_dependency_lock_contract.py`

**Interfaces:**
- Consumes: final lock workflow and regeneration script.
- Produces: beginner-readable refresh and review instructions.

- [ ] **Step 1: Add documentation contract assertions**

Require the uv version, cutoff, regeneration command, hash-install command, build isolation policy, and model edit boundary.

- [ ] **Step 2: Run focused tests and observe failure**

Run: `pytest -q tests/test_dependency_lock_contract.py`
Expected: FAIL until documentation is complete.

- [ ] **Step 3: Write documentation and changelog entry**

Explain intent, trust boundary, refresh sequence, reviewer checklist, and rollback.

- [ ] **Step 4: Run all verification**

Run: `ruff check .`, `python -m compileall -q src tests scripts`, doctests, full coverage, lock regeneration comparison, package build, hashed installed-wheel smoke, and `python -m pip check`.
Expected: all pass.

- [ ] **Step 5: Open one bounded PR**

Create one PR linked to issue #12, review all automated findings, re-run exact-head checks, and merge only after required gates pass.