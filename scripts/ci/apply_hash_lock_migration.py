"""Apply the reviewed hash-lock migration before deleting this bootstrap helper."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[2]


def _replace_exact(path: Path, old: str, new: str, *, count: int = 1) -> None:
    """Replace exactly ``count`` copies of ``old`` or fail closed."""

    text = path.read_text(encoding="utf-8")
    observed = text.count(old)
    if observed != count:
        raise RuntimeError(
            f"{path.relative_to(ROOT)}: expected {count} exact occurrence(s), "
            f"found {observed}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


def _patch_hourly_workflow() -> None:
    """Route model and independent verification through the reviewed lock."""

    path = ROOT / ".github/workflows/hourly-product-development.yml"
    _replace_exact(
        path,
        "cache-dependency-path: pyproject.toml",
        "cache-dependency-path: requirements/ci.lock",
        count=2,
    )
    _replace_exact(
        path,
        '''          agent_venv="${RUNNER_TEMP}/threadweave-agent-venv"
          python -m venv "$agent_venv"
          "$agent_venv/bin/python" -m pip install --upgrade pip
          "$agent_venv/bin/python" -m pip install \\
            -e ".[test]" \\
            "ruff==0.15.20" \\
            build
''',
        '''          agent_venv="${RUNNER_TEMP}/threadweave-agent-venv"
          python -m venv "$agent_venv"
          "$agent_venv/bin/python" -m pip install \\
            --require-hashes \\
            -r requirements/ci.lock
''',
    )
    _replace_exact(
        path,
        '''          python -m pip install --upgrade pip
          python -m pip install -e ".[test]" "ruff==0.15.20" build
''',
        '''          python -m pip install \\
            --require-hashes \\
            -r requirements/ci.lock
''',
    )
    _replace_exact(
        path,
        "          python -m build\n",
        "          python -m build --no-isolation\n",
    )
    _replace_exact(
        path,
        '''          temp_dir="$(mktemp -d)"
          python -m pip install --force-reinstall dist/*.whl
          (
''',
        '''          temp_dir="$(mktemp -d)"
          wheel_path="$(realpath "$(find dist -maxdepth 1 -name '*.whl' -print -quit)")"
          wheel_sha="$(sha256sum "$wheel_path" | awk '{print $1}')"
          wheel_requirements="$RUNNER_TEMP/threadweave-wheel.txt"
          printf 'threadweave @ file://%s \\\n    --hash=sha256:%s\\n' \\
            "$wheel_path" "$wheel_sha" >"$wheel_requirements"
          python -m pip install \\
            --require-hashes \\
            --no-deps \\
            --no-index \\
            --force-reinstall \\
            -r "$wheel_requirements"
          (
''',
    )


def _patch_workflow_contract_tests() -> None:
    """Replace obsolete unhashed-install assertions with lock contracts."""

    path = ROOT / "tests/test_workflows.py"
    text = path.read_text(encoding="utf-8")
    start = text.index(
        "def test_reverification_runs_the_complete_product_quality_gate():"
    )
    end = text.index(
        "def test_ci_overrides_package_only_coverage_source_for_autonomous_scripts():"
    )
    replacement = '''def test_reverification_runs_the_complete_product_quality_gate():
    """A fresh credential-free job proves the locked patch before publication."""
    workflow = _workflow("hourly-product-development.yml")

    assert "Set up independent Python verification" in workflow
    assert workflow.count("--require-hashes") >= 3
    assert workflow.count("-r requirements/ci.lock") >= 2
    assert "python -m build --no-isolation" in workflow
    assert "wheel_requirements=" in workflow
    assert "--no-index" in workflow
    assert "PIP_NO_INDEX=1" in workflow
    assert "ruff check ." in workflow
    assert "coverage run -m pytest -q" in workflow
    assert "coverage report" in workflow
    assert "python -m pip check" in workflow
    assert "git diff --check" in workflow
    assert "pip install --upgrade pip" not in workflow
    assert "pip install -e" not in workflow


def test_ci_regenerates_and_installs_only_the_reviewed_hash_lock():
    """Repository CI rejects stale locks and unhashed package installations."""
    workflow = _workflow("ci.yml")

    assert "lock-integrity:" in workflow
    assert (
        "astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990"
        in workflow
    )
    assert 'version: "0.11.29"' in workflow
    assert "bash scripts/ci/compile_ci_lock.sh" in workflow
    assert "cmp --silent requirements/ci.lock" in workflow
    assert workflow.count(
        "python -m pip install --require-hashes -r requirements/ci.lock"
    ) == 2
    assert "python -m build --no-isolation" in workflow
    assert "wheel_sha=" in workflow
    assert "--no-index" in workflow
    assert "pip install --upgrade pip" not in workflow
    assert "pip install -e" not in workflow


'''
    path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")


def _patch_readme() -> None:
    """Expose the reproducible supply-chain contract to package users."""

    path = ROOT / "README.md"
    marker = "## Autonomous maintenance\n"
    section = '''## Reproducible CI supply chain

ThreadWeave keeps its runtime dependency-free, but treats test and build tools as
executable supply-chain inputs. `requirements/ci.in` records exact direct intent;
a pinned uv compiler generates the universal `requirements/ci.lock` with
transitive SHA-256 hashes for Python 3.10-3.13. CI regenerates the lock and
requires a byte-for-byte match before installing it with pip hash-checking mode.
Builds run without isolation because the reviewed Hatchling backend is already
installed from that lock. See [`docs/supply-chain.md`](docs/supply-chain.md) for
the refresh procedure, reviewer checklist, and rollback contract.

'''
    _replace_exact(path, marker, section + marker)


def _patch_agents() -> None:
    """Make the beginner-facing verification instructions hash locked."""

    path = ROOT / "AGENTS.md"
    old = '''```bash
python -m pip install -e ".[test]" ruff build
ruff check .
python -m compileall -q src tests
python -m doctest \\
  src/threadweave/collation.py \\
  src/threadweave/dates.py \\
  src/threadweave/headers.py \\
  src/threadweave/subject.py
coverage run -m pytest -q
coverage report
python -m build
python -m pip check
```
'''
    new = '''```bash
python -m pip install --require-hashes -r requirements/ci.lock
ruff check .
python -m compileall -q src tests scripts
python -m doctest \\
  src/threadweave/collation.py \\
  src/threadweave/dates.py \\
  src/threadweave/headers.py \\
  src/threadweave/subject.py
coverage run -m pytest -q
coverage report
python -m build --no-isolation
python -m pip check
```

Regenerate dependency policy only through `scripts/ci/compile_ci_lock.sh` with
uv 0.11.29, then review the complete lock diff and follow
[`docs/supply-chain.md`](docs/supply-chain.md). Never bypass a hash mismatch by
adding an unhashed install or re-enabling isolated build resolution.
'''
    _replace_exact(path, old, new)


def _patch_changelog() -> None:
    """Record the user-visible release-hardening change under Unreleased."""

    path = ROOT / "CHANGELOG.md"
    marker = "## Unreleased\n\n"
    entry = (
        "- Hash-lock every CI, test, lint, coverage, and build dependency, "
        "regenerate the universal lock byte-for-byte with a pinned uv compiler, "
        "and reuse the same reviewed toolchain in autonomous verification.\n"
    )
    _replace_exact(path, marker, marker + entry)


def main() -> None:
    """Apply every deterministic migration step exactly once."""

    _patch_hourly_workflow()
    _patch_workflow_contract_tests()
    _patch_readme()
    _patch_agents()
    _patch_changelog()


if __name__ == "__main__":
    main()
