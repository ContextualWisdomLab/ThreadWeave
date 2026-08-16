# ThreadWeave Documentation Map

Use this file as the discoverable index for product, technical, architecture, safety, governance, and operating documentation.

| Area | Canonical document |
|---|---|
| Product requirements | [`docs/PRD.md`](docs/PRD.md) |
| Technical requirements | [`docs/TRD.md`](docs/TRD.md) |
| As-built architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| UML/runtime diagrams | [`docs/UML.md`](docs/UML.md) |
| Conceptual domain/ERD | [`docs/ERD.md`](docs/ERD.md) |
| Public API/version contract | [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) |
| Architecture decisions | [`docs/adr/README.md`](docs/adr/README.md) |
| Runtime/supply-chain security | [`docs/SECURITY.md`](docs/SECURITY.md) |
| Threat model | [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) |
| Data governance / privacy boundary | [`docs/DATA_GOVERNANCE.md`](docs/DATA_GOVERNANCE.md) |
| Test strategy | [`docs/TEST_STRATEGY.md`](docs/TEST_STRATEGY.md) |
| Operability/rollback | [`docs/OPERABILITY.md`](docs/OPERABILITY.md) |
| Hourly autonomous maintenance | [`docs/operations/hourly-autonomous-maintenance.md`](docs/operations/hourly-autonomous-maintenance.md) |
| Incident / RCA runbook | [`docs/INCIDENT_RUNBOOK.md`](docs/INCIDENT_RUNBOOK.md) |
| Release/provenance/licensing gate | [`docs/RELEASE_PROVENANCE.md`](docs/RELEASE_PROVENANCE.md) |
| Requirement/standard/evidence traceability | [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) |
| Documentation fitness / maturity audit | [`docs/DOCUMENTATION_AUDIT.md`](docs/DOCUMENTATION_AUDIT.md) |
| Standards and APA 7 references | [`docs/research/README.md`](docs/research/README.md) |
| Supply-chain procedure | [`docs/supply-chain.md`](docs/supply-chain.md) |
| Agent development policy | [`AGENTS.md`](AGENTS.md) |
| Agent context | [`CLAUDE.md`](CLAUDE.md) |
| User-facing product guide | [`README.md`](README.md) |
| Release history | [`CHANGELOG.md`](CHANGELOG.md) |

## Maturity labels

Documentation in this repository must distinguish:

- **implemented-main / IMPLEMENTED-ON-PROTECTED-MAIN**: present on protected `main`;
- **active-PR / IMPLEMENTED-ON-ACTIVE-PR**: implemented or designed only on an open PR;
- **proposed**: architectural decision under review;
- **conceptual**: domain/ERD concept without ThreadWeave-owned persistence;
- **host-owned**: responsibility belongs to naruon, an IMAP server, archive service, or another wrapper;
- **planned / known gap**: accepted requirement not yet implemented/proven.

PR #20 incremental mailbox state is active-PR/proposed until integrated. Sent-date ordering and RFC 5256 THREAD serialization are already implemented-main capabilities and must not be left in historical backlog lists. Python 3.14 CI/package support is a current known gap until it is implemented and proven on an exact head.

## Documentation fitness rule

`docs/DOCUMENTATION_AUDIT.md` is the reconstruction-oriented fitness record. It must distinguish design sufficiency from protected-main implementation sufficiency, identify missing or stale families, and prevent conversation-only decisions from being treated as durable architecture until they are captured in this graph.