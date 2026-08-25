# ThreadWeave Data Governance and Privacy Boundary

**Status:** Accepted architecture guidance for protected-main integration  
**Last reviewed:** 2026-08-10

ThreadWeave is an in-process library and does not own a customer database, tenant directory, retention service, identity provider, or durable audit store. Data governance is therefore a shared-boundary contract: ThreadWeave minimizes and constrains what its runtime needs; the host owns lawful purpose, authorization, retention, deletion, residency, and durable access evidence.

## Data classes

ThreadWeave may receive or derive metadata that can be personal or commercially sensitive:

- `Message-ID`, `References`, and `In-Reply-To` values;
- subject text and decoded header text;
- message dates and mailbox metadata;
- caller-owned payload references;
- sequence numbers and UIDs supplied by a host;
- future caller-owned stable keys and RFC 8474 identifiers if incremental state is integrated.

The core threading algorithm does not require message bodies, attachments, authentication tokens, passwords, cookies, or tenant credentials.

## Governance principles

1. **Purpose limitation:** callers supply only metadata required for the requested threading/projection operation.
2. **No blanket masking as a functional substitute:** identifiers and subjects may be needed for correct threading and reconciliation. Hosts should use purpose-bound access, selective disclosure, encryption, pseudonymous/opaque external handles, and bounded logging instead of destructively masking values before correctness-critical computation.
3. **No ambient persistence:** current ThreadWeave runtime keeps no database and opens no durable store.
4. **No ambient disclosure:** runtime code must not send metadata to network, LLM, analytics, or telemetry providers.
5. **Opaque payload ownership:** arbitrary `Message.payload` values remain caller-owned references and are not serialized into protocol output or structural snapshots by default.
6. **Minimum diagnostic disclosure:** failures should expose bounded error classes rather than dumping entire headers, payloads, or mailbox contents.

## Host responsibilities

A host such as naruon, an IMAP server, archive service, or migration product owns:

- tenant/user/mailbox authorization;
- legal basis, contractual purpose, and consent where applicable;
- encryption at rest/in transit and key management;
- retention, legal hold, export, deletion, and data-residency policy;
- access-purpose and privileged-access auditing;
- backup/recovery of source mailbox data;
- cross-tenant isolation and incident response;
- policy for logging or displaying subjects and identifiers.

ThreadWeave does not infer those policies from the data it receives.

## Logging guidance

Do not log complete subjects, Message-IDs, reference chains, or payload representations merely for routine observability. Prefer:

- operation type;
- package version;
- message/reference/root counts;
- bounded depth/cardinality summaries;
- failure class;
- elapsed/resource metrics;
- host correlation identifier that does not itself reveal mailbox content.

If a host elects to log content-bearing metadata for a defined troubleshooting purpose, it must apply its own authorization, retention, encryption, and access-review policy.

## Incremental-state boundary

PR #20 proposes payload-free snapshots and stable caller keys. Until that work is integrated, it remains IMPLEMENTED-ON-ACTIVE-PR. If a host persists a future public snapshot, the host must treat the snapshot and identity mappings according to its own data classification and retention policy. ThreadWeave's process-local snapshot format must never become an implicit tenant database or authorization record.

## PII deletion and correction

Current ThreadWeave has no durable copy to erase. Correct or delete source data in the host system and reconstruct any derived forest/projection/cache. If future ThreadWeave-owned persistence is ever proposed, a new ADR must define data-subject rights, retention, erasure, backup propagation, tenant authority, migration, and audit evidence before implementation.

## Compliance posture

ThreadWeave may provide technical controls useful to a host's broader security/compliance program, but the library does not claim CSAP, SOC 2, ISO/IEC 27001, or other certification by itself. Evidence should distinguish library controls from host/platform controls.

## Verification

Tests and reviews should continue to prove that:

- core runtime performs no network/database/model I/O;
- protocol output excludes arbitrary payload objects;
- future structural snapshots exclude arbitrary payloads;
- errors do not require full message-body disclosure;
- documentation keeps tenant/retention/audit authority in the host boundary.