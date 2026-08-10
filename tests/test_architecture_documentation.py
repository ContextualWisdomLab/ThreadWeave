"""Contract tests for durable product and architecture documentation."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCUMENTS = (
    "DOCUMENTATION.md",
    "docs/PRD.md",
    "docs/TRD.md",
    "ARCHITECTURE.md",
    "docs/UML.md",
    "docs/ERD.md",
    "docs/API_CONTRACT.md",
    "docs/SECURITY.md",
    "docs/THREAT_MODEL.md",
    "docs/DATA_GOVERNANCE.md",
    "docs/TEST_STRATEGY.md",
    "docs/OPERABILITY.md",
    "docs/INCIDENT_RUNBOOK.md",
    "docs/RELEASE_PROVENANCE.md",
    "docs/TRACEABILITY.md",
    "docs/DOCUMENTATION_AUDIT.md",
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


def test_documentation_index_links_major_contracts() -> None:
    """Keep every canonical product, architecture, and operating doc linked."""

    documentation = _read("DOCUMENTATION.md")
    for relative_path in REQUIRED_DOCUMENTS[1:]:
        assert f"]({relative_path})" in documentation, (
            f"documentation index does not link {relative_path}"
        )


def test_active_incremental_work_is_not_claimed_as_protected_main() -> None:
    """Prevent the open incremental PR from becoming a false mainline claim."""

    prd = _read("docs/PRD.md")
    architecture = _read("ARCHITECTURE.md")
    erd = _read("docs/ERD.md")
    audit = _read("docs/DOCUMENTATION_AUDIT.md")
    assert "ACTIVE-PR" in prd
    assert "PR #20" in prd
    assert "not protected-main" in prd.lower()
    assert "PR #20" in architecture
    assert "not protected-main" in architecture.lower()
    assert "PR #20" in erd
    assert "persists no database entities" in erd
    assert "ACTIVE-PR" in erd
    assert "not protected-main" in erd.lower()
    assert "IMPLEMENTED-ON-ACTIVE-PR" in audit
    assert "Draft PR #20" in audit


def test_adr_index_keeps_incremental_decision_proposed() -> None:
    """Require the incremental-state ADR to remain proposed until integration."""

    index = _read("docs/adr/README.md")
    decision = _read("docs/adr/0004-incremental-state-boundary.md")
    assert "0004-incremental-state-boundary.md" in index
    assert any(
        row.rstrip().endswith("| Proposed |")
        for row in index.splitlines()
        if "[ADR-0004](0004-incremental-state-boundary.md)" in row
    )
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


def test_documentation_audit_distinguishes_design_from_main_sufficiency() -> None:
    """A complete-looking design pack must not masquerade as protected-main truth."""

    audit = _read("docs/DOCUMENTATION_AUDIT.md")
    assert "DESIGN-SUFFICIENT" in audit
    assert "PROTECTED-MAIN-INSUFFICIENT" in audit
    assert "100% production statement/branch coverage | PARTIAL" in audit
    assert "Python 3.14 CI/package compatibility" in audit
    assert (
        "| Python 3.14 CI/package compatibility | IMPLEMENTED-ON-ACTIVE-PR |"
        in audit
    )
    assert "PR #27" in audit
    assert "thread_email_messages" in audit
    assert "Message.sequence_number" in audit
    assert "public THREAD identifier" in audit


def test_governance_preserves_useful_metadata_without_blanket_masking() -> None:
    """Keep PII governance purpose-bound without destroying threading inputs."""

    governance = _read("docs/DATA_GOVERNANCE.md")
    assert "No blanket masking as a functional substitute" in governance
    assert "purpose-bound access" in governance
    assert "host" in governance.lower()
    assert "ThreadWeave has no durable copy to erase" in governance


def test_incident_runbook_requires_root_cause_and_exact_evidence_identity() -> None:
    """Incident handling must fix the owning layer and preserve evidence identity."""

    runbook = _read("docs/INCIDENT_RUNBOOK.md")
    assert "Fix the owning layer" in runbook
    assert "contributor head" in runbook
    assert "PR base snapshot" in runbook
    assert "current protected/live base tip" in runbook
    assert "A queued or externally unavailable reviewer/check is an item-local state" in runbook
    assert "host-provided protocol metadata" in runbook
    assert "thread_email_messages" in runbook
    assert "one-based input position only as an internal ordering fallback" in runbook
    assert "known product-contract mismatch" in runbook


def test_release_gate_requires_trusted_publication_and_post_publish_smoke() -> None:
    """A merge alone must never be represented as a completed public release."""

    release = _read("docs/RELEASE_PROVENANCE.md")
    agent_context = _read("CLAUDE.md")
    assert "A merge is not a release" in release
    assert "Trusted Publishing" in release
    assert (
        "Do not introduce a long-lived PyPI token or manual artifact upload to bypass "
        "failed OIDC/Trusted Publishing"
    ) in release
    assert "post-publication clean-install smoke" in release
    assert "Apache-2.0" in release
    assert (
        "`COPILOT_GITHUB_TOKEN` is not a development-model credential and must not "
        "be introduced into the autonomous development path."
    ) in agent_context
    assert (
        "Scheduled autonomous development uses an immutably pinned OpenCode Agent "
        "and `NVIDIA_NIM_API_KEY` only for actual model-backed execution."
    ) in agent_context


def test_autonomy_and_evidence_identity_adrs_are_accepted_and_indexed() -> None:
    """Persist work-conserving continuation and exact evidence identities as ADRs."""

    index = _read("docs/adr/README.md")
    autonomy = _read("docs/adr/0006-work-conserving-autonomous-maintenance.md")
    evidence = _read("docs/adr/0007-exact-evidence-identity.md")
    assert "0006-work-conserving-autonomous-maintenance.md" in index
    assert "0007-exact-evidence-identity.md" in index
    assert "**Status:** Accepted" in autonomy
    assert "NVIDIA_NIM_API_KEY" in autonomy
    assert "COPILOT_GITHUB_TOKEN" in autonomy
    assert "double exit sweep" in autonomy
    assert "**Status:** Accepted" in evidence
    assert "contributor head SHA" in evidence
    assert "live protected-base tip SHA" in evidence
