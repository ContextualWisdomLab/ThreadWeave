# Hash-Locked CI Supply Chain Design

## Objective

Replace every network-backed Python tooling installation in ThreadWeave CI and autonomous verification with one reviewable, universal, hash-locked requirements file. The runtime package remains pure standard library with zero runtime dependencies.

## Chosen approach

Use uv `0.11.29` only as a deterministic lock compiler. A small direct-input file pins the CI, test, lint, coverage, build frontend, and Hatchling backend versions. uv compiles that input with `--universal`, `--python-version 3.10`, `--generate-hashes`, and a fixed `--exclude-newer` cutoff into a pip-compatible lock. GitHub Actions installs the lock with `python -m pip install --require-hashes` on Python 3.10 through 3.13.

This is preferred over a project-only `uv.lock` because OpenSSF Scorecard explicitly identified unhashed `pip` commands, the repository already uses pip-compatible workflows, and a regenerated requirements lock can be compared byte-for-byte without changing the package's runtime or developer-facing project model.

## Components

### `requirements/ci.in`

Contains only exact direct pins:

- `build==1.5.0`
- `coverage[toml]==7.15.3`
- `hatchling==1.31.0`
- `pytest==9.1.1`
- `ruff==0.15.20`

The file is the reviewed dependency intent. `pyproject.toml` uses the same exact Hatchling, coverage, and pytest pins so package metadata and CI intent cannot drift silently.

### `requirements/ci.lock`

Generated, universal pip requirements with every transitive dependency version and every accepted distribution SHA-256. Platform and Python markers remain in the generated output so one lock supports Linux CI on Python 3.10-3.13.

### `scripts/ci/compile_ci_lock.sh`

The sole supported regeneration entry point. It requires uv `0.11.29`, uses a fixed RFC 3339 upload cutoff, generates output without a path-dependent header, and accepts an optional destination so CI can regenerate into a temporary file and compare exact bytes.

### CI contract

A dedicated lock-integrity job installs a full-SHA-pinned `astral-sh/setup-uv` action, pins the uv binary version, regenerates the lock, and requires an exact byte match. Test and package jobs install only `requirements/ci.lock` with `--require-hashes`.

Package builds use `python -m build --no-isolation`, because Hatchling and the build frontend were already installed from the reviewed lock. The installed-wheel smoke test computes the newly built wheel's SHA-256 and installs it from a temporary local requirements file with `--require-hashes --no-deps --no-index`.

### Autonomous workflow contract

The model workspace receives the already locked CI tool environment but still has no index access, Git metadata, GitHub credentials, or permission to edit dependency policy. Independent verification installs the same lock on a fresh credential-free runner and builds without isolation.

## Failure behavior

The pipeline fails closed when:

- the direct input or `pyproject.toml` pins drift;
- the generated lock differs byte-for-byte;
- a dependency line lacks hashes;
- pip cannot find a listed artifact matching a reviewed hash;
- an isolated build tries to resolve an unreviewed backend;
- the local wheel digest does not match the temporary installation requirement;
- the autonomous model changes dependency, workflow, or lock files.

## Testing

Contract tests inspect all workflows and policy files. They require full action SHAs, the exact uv version and cutoff, `--require-hashes` for every dependency installation, `--no-isolation` for builds, and synchronized direct pins. Existing production and autonomous-boundary coverage remains 100%.

## Documentation and release impact

README, AGENTS, supply-chain documentation, and CHANGELOG describe regeneration, provenance, and review rules. This change is release hardening only; it does not change ThreadWeave runtime behavior or by itself justify a semantic-version bump.