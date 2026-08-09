"""Contract tests for durable product and architecture documentation."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCUMENTS = (
    "docs/PRD.md",
    "docs/TRD.md",
    "ARCHITECTURE.md",
    "docs/UML.md",
    "docs/ERD.md",
    "docs/API_CONTRACT.md",
    "docs/SECURITY.md",
    "docs/THREAT_MODEL.md",
    "docs/TEST_STRATEGY.md",
    "docs/OPERABILITY.md",
    "docs/TRACEABILITY.md",
    "docs/adr/README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "CHANGELOG.md",
)


def _read(relative_path: str) -> str:
    """Return one repository document as UTF-8 text."""

    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_canonical_product_architecture_documents_exist() -> None:
    """Keep the complete discoverable documentation graph in the repository."""

    missing = [path for path in REQUIRED_DOCUMENTS if not (ROOT / path).is_file()]
    assert not missing, f"missing canonical documentation: {missing}"


def test_active_incremental_work_is_not_claimed_as_protected_main() -> None:
    """Prevent the open incremental PR from becoming a false mainline claim."""

    prd = _read("docs/PRD.md")
    architecture = _read("ARCHITECTURE.md")
    erd = _read("docs/ERD.md")
    assert "ACTIVE-PR" in prd
    assert "PR #20" in prd
    assert "not protected-main" in prd.lower()
    assert "PR #20" in architecture
    assert "not protected-main" in architecture.lower()
    assert "PR #20" in erd
    assert "persists no database entities" in erd


def test_adr_index_keeps_incremental_decision_proposed() -> None:
    """Require the incremental-state ADR to remain proposed until integration."""

    index = _read("docs/adr/README.md")
    decision = _read("docs/adr/0004-incremental-state-boundary.md")
    assert "0004-incremental-state-boundary.md" in index
    assert "Proposed" in index
    assert "**Status:** Proposed" in decision
    assert "PR #20" in decision


def test_domain_erd_does_not_invent_threadweave_persistence() -> None:
    """Keep host-owned persistence outside the ThreadWeave product boundary."""

    erd = _read("docs/ERD.md")
    architecture = _read("ARCHITECTURE.md")
    assert "Host persistence is external" in erd
    assert "ThreadWeave does not define the host schema" in erd
    assert "no database driver" in architecture
    assert "Host-service boundary" in architecture
