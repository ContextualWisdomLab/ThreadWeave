"""Apply only the remaining hash-lock changes to the hourly workflow."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "hourly-product-development.yml"


def _replace_exact(old: str, new: str, *, count: int = 1) -> None:
    """Replace exactly ``count`` workflow fragments or fail closed."""

    text = WORKFLOW.read_text(encoding="utf-8")
    observed = text.count(old)
    if observed != count:
        raise RuntimeError(
            f"hourly workflow: expected {count} exact occurrence(s), found {observed}"
        )
    WORKFLOW.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    """Route model and independent verification through the reviewed lock."""

    _replace_exact(
        "cache-dependency-path: pyproject.toml",
        "cache-dependency-path: requirements/ci.lock",
        count=2,
    )
    _replace_exact(
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
        '''          python -m pip install --upgrade pip
          python -m pip install -e ".[test]" "ruff==0.15.20" build
''',
        '''          python -m pip install \\
            --require-hashes \\
            -r requirements/ci.lock
''',
    )
    _replace_exact(
        "          python -m build\n",
        "          python -m build --no-isolation\n",
    )
    _replace_exact(
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


if __name__ == "__main__":
    main()
