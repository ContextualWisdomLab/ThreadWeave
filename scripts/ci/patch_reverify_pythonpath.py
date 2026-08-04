"""Add the source-layout import path to independent autonomous verification."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "hourly-product-development.yml"
TESTS = ROOT / "tests" / "test_workflows.py"


def _replace_exact(path: Path, old: str, new: str) -> None:
    """Replace one exact fragment or fail closed before writing."""

    text = path.read_text(encoding="utf-8")
    observed = text.count(old)
    if observed != 1:
        raise RuntimeError(f"{path.relative_to(ROOT)}: expected one fragment, found {observed}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    """Patch the verifier job and its regression contract together."""

    _replace_exact(
        WORKFLOW,
        '''    permissions:
      actions: read
      contents: read
      pull-requests: read
    outputs:
''',
        '''    permissions:
      actions: read
      contents: read
      pull-requests: read
    env:
      PYTHONPATH: src
    outputs:
''',
    )
    _replace_exact(
        TESTS,
        '''    assert "Set up independent Python verification" in workflow
    assert workflow.count("--require-hashes") >= 3
''',
        '''    assert "Set up independent Python verification" in workflow
    reverify = workflow.split("  reverify-product-gap:", 1)[1].split(
        "  publish-product-gap:", 1
    )[0]
    assert "PYTHONPATH: src" in reverify
    assert workflow.count("--require-hashes") >= 3
''',
    )


if __name__ == "__main__":
    main()
