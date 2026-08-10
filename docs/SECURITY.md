# ThreadWeave Security Contract

**Status:** Accepted for protected-main runtime and repository trust boundaries.  
**Last reviewed:** 2026-08-09

## Security objective

Keep email metadata parsing/threading deterministic and capability-poor, fail closed at protocol and graph boundaries, and keep autonomous development credentials/authority outside repository-controlled execution.

## Assets

- correctness of thread structure and protocol identifiers;
- integrity of caller-owned payload references;
- mailbox metadata supplied by the host;
- package source, CI/release artifacts, dependency locks, and signatures/hashes;
- NVIDIA/GitHub/OIDC/reviewer/release credentials used only by automation;
- future incremental snapshots if ADR-0004 is accepted.

## Runtime trust boundary

Runtime message fields and payloads are untrusted caller data. The package itself has no network, database, shell, cloud-provider, or credential capability. It does not render HTML, execute message content, or follow URLs.

### Required runtime controls

- normalize and validate protocol identifiers before graph/projection use;
- terminate on cycles/shared-node violations where the public boundary requires a tree;
- avoid recursion proportional to hostile mailbox depth;
- reject invalid/bool/out-of-range/duplicate IMAP identifiers;
- prevent CR/LF or framing injection in protocol output;
- treat arbitrary `payload` as opaque and never serialize it accidentally;
- use deterministic Unicode comparison rules rather than locale/environment state;
- preserve source structures when producing filtered protocol projections.

## Header and Unicode risk

Malformed RFC 2047/5322 data is common in historical mail. Defensive parsing may preserve a literal value when safe, but must not convert malformed metadata into graph corruption or executable content. Unicode casemap normalization intentionally does not collapse visual confusables across scripts; UI hosts may add separate spoofing warnings without changing ThreadWeave identity semantics.

## Graph denial-of-service controls

Deep chains, cycles, repeated references, large sibling sets, and adversarial dummy structures are expected hostile shapes. Core traversal and protocol rendering must remain iterative/identity-guarded. Complexity/performance changes require representative large/deep regression or benchmark evidence.

## Host-service responsibilities

ThreadWeave does not authenticate or authorize users. Hosts must secure:

- mailbox/tenant access;
- persistent message bodies and headers;
- database/session credentials;
- sequence/UID assignment and mailbox synchronization;
- distributed write serialization;
- API rate limits and audit;
- snapshot storage if incremental state is adopted.

Hosts must never infer authorization from Message-ID, THREADID, EMAILID, sequence number, UID, or Python object identity.

## Automation and supply-chain boundary

The model-backed development workflow follows ADR-0005:

- repository/model execution receives no GitHub write/release/OIDC credentials;
- NVIDIA model credentials remain inside the brokered privileged boundary and are not materialized into repository-controlled code;
- verification is performed in a fresh credential-free context;
- publication opens a PR only after validating a sealed patch;
- central review/security/merge remains independent;
- release credentials are used only after protected-main acceptance.

GitHub Actions and third-party actions are pinned to immutable reviewed commit SHAs. CI/build dependencies are exact and hash-locked where repository policy provides a lock.

## PII and privacy

ThreadWeave operates on message metadata that can be personal data. The library must not solve privacy by silently masking or changing Message-ID, subject, timestamps, or reference relationships because doing so can destroy threading correctness. Instead, hosts should use purpose-bound authorization, least-privilege service identity, encrypted storage/transport, bounded retention, controlled export, and auditable access. Tests/fixtures must use synthetic or appropriately licensed non-sensitive data.

## Vulnerability handling

Security reports should identify the affected version/commit, public API boundary, input shape, impact, and minimal reproduction without including real private email content. A fix should add a regression at the violated boundary and verify package, protocol, and supply-chain gates.

## Release security gate

No release is security-ready while required exact-head SAST/security/supply-chain checks are failed, cancelled, skipped-required, absent, pending, or stale. Local success is supporting evidence, not a substitute for required protected-head gates.