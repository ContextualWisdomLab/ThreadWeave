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
    "docs/operations/hourly-autonomous-maintenance.md",
    "docs/INCIDENT_RUNBOOK.md",
    "docs/RELEASE_PROVENANCE.md",
    "docs/TRACEABILITY.md",
    "docs/DOCUMENTATION_AUDIT.md",
    "docs/adr/README.md",
    "docs/product-technical-gap-baseline.md",
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


def test_readme_stays_customer_operator_first() -> None:
    """Keep the package front page a standalone/host guide, not a bot playbook."""

    readme = _read("README.md")
    operations = _read("docs/operations/hourly-autonomous-maintenance.md")
    playbook_markers = (
        "hourly-pr-maintenance.yml",
        "hourly-product-development.yml",
        "NVIDIA_NIM_API_KEY",
        "PR_REVIEW_MERGE_TOKEN",
        "OPENCODE_APPROVE_TOKEN",
    )

    assert "pip install threadweave" in readme
    assert "from threadweave import" in readme
    assert "thread_messages" in readme
    assert "naruon" in readme.lower()
    assert "docs/operations/hourly-autonomous-maintenance.md" in readme
    assert "## autonomous maintenance" not in readme.lower()
    for marker in playbook_markers:
        assert marker not in readme, f"README still embeds playbook detail: {marker}"
        assert marker in operations, f"operations playbook is missing {marker}"
    assert "do not merge" in operations.lower() or "never merges" in operations.lower()
    assert "dry_run" in operations


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


def test_documentation_audit_records_protected_main_sufficiency() -> None:
    """Keep integrated documentation maturity separate from release readiness."""

    audit = _read("docs/DOCUMENTATION_AUDIT.md")
    assert "DESIGN-SUFFICIENT" in audit
    assert "PROTECTED-MAIN-DOCUMENTATION-SUFFICIENT" in audit
    assert "RELEASE-INSUFFICIENT" in audit
    assert "100% production statement/branch coverage | IMPLEMENTED-ON-PROTECTED-MAIN" in audit
    assert "protected-main push CI run `31354471651`" in audit
    assert "Python 3.10–3.14 CI/package compatibility" in audit
    assert (
        "| Python 3.10–3.14 CI/package compatibility | "
        "IMPLEMENTED-ON-PROTECTED-MAIN |"
        in audit
    )
    assert "PR #27 merge `4fa4caf`" in audit
    assert (
        "| canonical documentation reconstruction graph | "
        "IMPLEMENTED-ON-PROTECTED-MAIN |"
    ) in audit
    assert "PR #25 merge `fe9b46f`" in audit


def test_python_314_claim_is_protected_main_and_cross_document_consistent() -> None:
    """Keep Python 3.14 compatibility aligned with package metadata and docs."""

    pyproject = _read("pyproject.toml")
    prd = _read("docs/PRD.md")
    trd = _read("docs/TRD.md")
    architecture = _read("ARCHITECTURE.md")
    documentation = _read("DOCUMENTATION.md")
    traceability = _read("docs/TRACEABILITY.md")
    agent_context = _read("CLAUDE.md")

    assert '"Programming Language :: Python :: 3.14"' in pyproject
    assert "Python 3.10–3.14 support on protected main" in prd
    assert "Python support: 3.10–3.14" in trd
    assert "Protected `main` supports Python 3.10 through 3.14" in architecture
    assert "Python 3.14 CI/package support is implemented-main" in documentation
    assert "Python 3.14 compatibility" in traceability
    assert "implemented-main" in traceability
    assert "Protected main currently proves Python 3.10–3.14" in agent_context
    assert "current gap until implemented" not in agent_context
    assert "current known gap" not in documentation


def test_api_contract_keeps_internal_order_separate_from_public_identifiers() -> None:
    """Iterable position must never become implicit public mailbox identity."""

    contract = _read("docs/API_CONTRACT.md")
    prd = _read("docs/PRD.md")
    assert "does **not** derive public sequence-number or UID metadata" in contract
    assert "one-based input position only as an internal deterministic ordering fallback" in contract
    assert "`thread_email_messages(...)` SHALL NOT turn iterable position" in prd
    assert "public mailbox sequence or UID metadata" in prd


def test_api_contract_requires_exact_owned_coverage_for_public_changes() -> None:
    """Public API change control must preserve the repository's exact coverage gate."""

    contract = _read("docs/API_CONTRACT.md")
    assert "100% owned production statement coverage" in contract
    assert "100% owned production branch coverage" in contract
    assert "focused and full verification" in contract


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
    assert "protected-main PR #26" in runbook
    assert "leaves public `sequence_number`/UID metadata unset" in runbook


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


def test_trusted_release_identity_adr_is_accepted_and_indexed() -> None:
    """Persist the non-bypass Trusted Publishing boundary as an architecture decision."""

    index = _read("docs/adr/README.md")
    decision = _read("docs/adr/0008-trusted-release-identity-boundary.md")
    release = _read("docs/RELEASE_PROVENANCE.md")
    traceability = _read("docs/TRACEABILITY.md")

    assert "0008-trusted-release-identity-boundary.md" in index
    assert "**Status:** Accepted" in decision
    assert "pre-created" in decision
    assert "prevent self-review" in decision
    assert "protected branches" in decision
    assert "long-lived PyPI token" in decision
    assert "manual upload" in decision
    assert "release-readiness" in release
    assert "ADR-0008" in traceability


def test_lineage_evidence_consumer_boundary_adr_is_proposed_and_indexed() -> None:
    """Keep the naruon/LineageWeave boundary a documentation-only ADR, not a runtime coupling."""

    index = _read("docs/adr/README.md")
    decision = _read("docs/adr/0009-lineage-evidence-consumer-boundary.md")
    traceability = _read("docs/TRACEABILITY.md")

    assert "0009-lineage-evidence-consumer-boundary.md" in index
    assert any(
        row.rstrip().endswith("| Proposed |")
        for row in index.splitlines()
        if "[ADR-0009](0009-lineage-evidence-consumer-boundary.md)" in row
    )
    assert "**Status:** Proposed" in decision
    assert "naruon#1437" in decision
    assert "LineageWeave#338" in decision
    assert "ThreadWeave remains completely unaware of LineageWeave" in decision
    assert "RFC 8474" in decision
    assert "ADR-0009" in traceability

    # Lock the branched dependency ordering at RELATION level: two separate
    # edges must be stated explicitly, not a single sequential chain.
    #   Edge A: naruon#1437 -> naruon#1350 -> ThreadWeave PR #20
    #   Edge B: naruon#1437 -> LineageWeave#338
    flat_decision = " ".join(decision.split())
    assert (
        "`naruon#1437` depends on `naruon#1350`, which depends on ThreadWeave PR #20"
        in flat_decision
    )
    assert "`naruon#1437` also depends on `LineageWeave#338`" in flat_decision
    # The separate-branch wording ("also depends") must exist so a reader cannot
    # misread the two relations as one transitive chain through naruon#1350.
    assert "also depends" in decision


def test_gap_baseline_tracks_lineageweave_cross_repository_chain() -> None:
    """Record the confirmed naruon/LineageWeave dependency chain and open PR/issue inventory."""

    gap_baseline = _read("docs/product-technical-gap-baseline.md")
    documentation_map = _read("DOCUMENTATION.md")

    assert "product-technical-gap-baseline.md" in documentation_map
    assert "ThreadWeave has no production-integration PR or issue that mentions LineageWeave" in gap_baseline
    assert "naruon#1437" in gap_baseline
    assert "naruon#1350" in gap_baseline
    assert "LineageWeave#338" in gap_baseline
    assert "ADR-0009" in gap_baseline
    assert "#20" in gap_baseline
    assert "#32" in gap_baseline
    assert "#17" in gap_baseline
    assert "Not applicable to this repository" in gap_baseline
    assert "Storybook" in gap_baseline

    # Relation-level lock of the branched chain as recorded in the baseline
    # (mirrors ADR-0009's two-edge statement; no sequential-chain reading).
    # Whitespace-normalized so markdown line wrapping cannot hide a relation.
    flat = " ".join(gap_baseline.split())
    assert (
        "`naruon#1437` depends on `naruon#1350`, which depends on ThreadWeave PR #20"
        in flat
    )
    assert "`naruon#1437` also depends on `LineageWeave#338`" in flat
