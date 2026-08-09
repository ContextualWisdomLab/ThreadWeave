# ThreadWeave Documentation Map

Use this file as the discoverable index for product, technical, architecture, safety, and operating documentation.

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
| Test strategy | [`docs/TEST_STRATEGY.md`](docs/TEST_STRATEGY.md) |
| Operability/rollback/release | [`docs/OPERABILITY.md`](docs/OPERABILITY.md) |
| Requirement/standard/evidence traceability | [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) |
| Standards and APA 7 references | [`docs/research/README.md`](docs/research/README.md) |
| Supply-chain procedure | [`docs/supply-chain.md`](docs/supply-chain.md) |
| Agent development policy | [`AGENTS.md`](AGENTS.md) |
| Agent context | [`CLAUDE.md`](CLAUDE.md) |
| User-facing product guide | [`README.md`](README.md) |
| Release history | [`CHANGELOG.md`](CHANGELOG.md) |

## Maturity labels

Documentation in this repository must distinguish:

- **implemented-main**: present on protected `main`;
- **active-PR**: implemented or designed only on an open PR;
- **proposed**: architectural decision under review;
- **conceptual**: domain/ERD concept without ThreadWeave-owned persistence;
- **host-owned**: responsibility belongs to naruon, an IMAP server, archive service, or another wrapper.

PR #20 incremental mailbox state is active-PR/proposed until integrated. Sent-date ordering and RFC 5256 THREAD serialization are already implemented-main capabilities and must not be left in historical backlog lists.