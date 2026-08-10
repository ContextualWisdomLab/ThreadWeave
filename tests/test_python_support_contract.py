"""Contract tests for the declared and exercised Python support range."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility path.
    import tomli as tomllib


ROOT = Path(__file__).parents[1]


def test_python_314_is_declared_exercised_and_documented() -> None:
    """Keep Python 3.14 metadata, CI, and user documentation in one support contract."""

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    classifiers = project["project"]["classifiers"]
    ci_workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    supply_chain = (ROOT / "docs/supply-chain.md").read_text(encoding="utf-8")

    assert project["project"]["requires-python"] == ">=3.10"
    assert "Programming Language :: Python :: 3.14" in classifiers
    assert 'python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]' in ci_workflow
    assert "supports Python 3.10 through 3.14" in readme
    assert "Python 3.10 through 3.14" in supply_chain
