# ThreadWeave Architecture Decision Record Index

The status inside each ADR is authoritative. `Accepted` means the decision governs architecture; it does not by itself prove every described target capability is implemented. Protected-main implementation maturity is tracked in PRD/TRD/Architecture and exact repository evidence.

| ADR | Decision | Status |
|---|---|---|
| [ADR-0001](0001-canonical-batch-oracle.md) | Preserve one canonical batch threading oracle. | Accepted |
| [ADR-0002](0002-transport-neutral-core.md) | Keep threading independent from protocol sessions and persistence. | Accepted |
| [ADR-0003](0003-optional-subject-date-policies.md) | Keep subject grouping and sent-date ordering explicit policies. | Accepted |
| [ADR-0004](0004-incremental-state-boundary.md) | Add bounded incremental state only as a batch-oracle-preserving extension. | Proposed |
| [ADR-0005](0005-automation-authority-separation.md) | Separate model development, verification, publication, review, merge, and release authority. | Accepted |
| [ADR-0006](0006-work-conserving-autonomous-maintenance.md) | Keep hourly maintenance work-conserving; external waiting blocks only the affected item. | Accepted |
| [ADR-0007](0007-exact-evidence-identity.md) | Distinguish contributor head, PR base snapshot, live protected-base tip, synthetic merge, and tested checkout evidence. | Accepted |
| [ADR-0008](0008-trusted-release-identity-boundary.md) | Fail closed on pre-created protected GitHub/PyPI release identity before irreversible release side effects. | Accepted |
| [ADR-0010](0010-actions-registry-lifecycle-evidence.md) | Separate Actions registry observation (read-only audit) from workflow-disable authority (a separate, out-of-band operator action). | Accepted |

## Status vocabulary

- `Proposed`: under review; not an as-built product claim.
- `Accepted`: governing decision.
- `Deprecated`: retained for compatibility but not preferred for new work.
- `Superseded`: replaced by a named later ADR.
- `Rejected`: evaluated and intentionally not adopted.

## ADR required when

A change alters the canonical threading oracle, protocol/session boundary, persistence ownership, public identity semantics, durable snapshot schema, Unicode/collation contract, ordering policy defaults, runtime dependency/capability surface, autonomous/release authority boundary, work-conserving loop semantics, review/merge/release evidence identity, or trusted-publication identity/protection policy.

Implementation PRs should cite the applicable ADRs and update PRD/TRD/UML/ERD/security/test/operability/traceability/documentation-audit records when those contracts move.