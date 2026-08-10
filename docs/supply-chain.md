# CI dependency supply chain

ThreadWeave has no runtime dependencies. Python packages used for tests, linting,
coverage, and builds are nevertheless executable supply-chain inputs, so CI accepts
them only through the reviewed hash lock at `requirements/ci.lock`.

## Trust model

- `requirements/ci.in` contains exact direct pins.
- `scripts/ci/compile_ci_lock.sh` is the only supported lock compiler.
- The compiler requires **uv 0.11.29** and limits candidate artifacts to uploads
  before **2026-08-04T00:00:00Z**.
- `--universal` and `--python-version 3.10` produce one marker-aware lock for the
  supported Python 3.10 through 3.14 matrix.
- `--generate-hashes` records reviewed SHA-256 values for every transitive
  distribution accepted by pip hash-checking mode.
- GitHub Actions regenerates the lock and requires a byte-for-byte match before
  running the rest of CI.
- Every network-backed installation uses:

  ```bash
  python -m pip install --require-hashes -r requirements/ci.lock
  ```

- Builds use the already locked frontend and Hatchling backend:

  ```bash
  python -m build --no-isolation
  ```

The autonomous model cannot edit `.github/`, `scripts/`, `pyproject.toml`, or
`requirements/`. It receives no package-index access while authoring a product
patch. A fresh credential-free verifier independently installs this lock and
re-runs all package gates before publication.

## Supported-interpreter evidence

Python 3.14 support is not inferred from `requires-python >=3.10`. It requires an
actual Python 3.14 GitHub Actions test lane plus package build/install smoke under
Python 3.14. The supported range therefore remains a synchronized contract across
`pyproject.toml`, `.github/workflows/ci.yml`, README, this document, and the
support-contract regression test.

## Refresh procedure

1. Change one or more exact direct pins in `requirements/ci.in`.
2. Keep the matching Hatchling, coverage, and pytest pins synchronized in
   `pyproject.toml`.
3. Deliberately advance `EXCLUDE_NEWER` in
   `scripts/ci/compile_ci_lock.sh` only when newly published artifacts are meant
   to enter the reviewed resolution.
4. Install the pinned compiler and regenerate:

   ```bash
   uv --version  # must report 0.11.29
   bash scripts/ci/compile_ci_lock.sh
   ```

5. Review the complete `requirements/ci.lock` diff. Confirm that every package is
   version-pinned, every block has SHA-256 hashes, markers still cover Python
   3.10 through 3.14, and no URL, VCS, editable, or local source entered the lock.
6. Validate the exact lock:

   ```bash
   python -m pip install --require-hashes -r requirements/ci.lock
   tmp_lock="$(mktemp)"
   bash scripts/ci/compile_ci_lock.sh "$tmp_lock"
   cmp --silent requirements/ci.lock "$tmp_lock"
   ```

7. Run the full verification suite and include the lock provenance in the pull
   request description.

## Reviewer checklist

- The setup-uv action and all other Actions use full commit SHAs.
- The uv binary version and upload cutoff are explicit.
- Direct pins are intentional and synchronized with `pyproject.toml`.
- No pip upgrade, unhashed remote install, or isolated build resolution remains.
- The lock diff contains only expected packages, versions, markers, and hashes.
- Python 3.10 through 3.14 all install the exact reviewed lock successfully.
- Runtime dependencies remain empty.
- The model-facing workflow still denies dependency-policy edits and index access.

## Rollback

Revert the dependency-policy commit as one unit: `requirements/ci.in`,
`requirements/ci.lock`, compiler script, metadata pins, workflows, and docs. Do
not retain a newer lock with older direct pins or reintroduce an unhashed install
as a temporary workaround. If a locked artifact becomes unavailable or unsafe,
open a focused dependency update, select a new exact pin and cutoff, regenerate,
and re-run the complete exact-head security and package gates.
