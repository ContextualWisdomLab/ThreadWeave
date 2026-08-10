# ThreadWeave Technical Requirements Document

**Status:** Accepted baseline for protected `main` at `4fa4caf86651193497002a3730ec19d8917f8818`  
**Last reviewed:** 2026-08-10

## 1. Technical objective

Implement RFC-grounded email conversation threading as a deterministic, zero-runtime-dependency Python kernel whose protocol presentation, optional ordering, adapters, automation, and future incremental state remain separable. The canonical batch algorithm is the structural oracle.

## 2. As-built package boundaries

| Module | Responsibility | Excluded responsibility |
|---|---|---|
| `headers` | normalize Message-ID and reference header identifiers | graph ownership, I/O |
| `encoded_words` | defensive RFC 2047 text decoding | MIME body rendering |
| `subject` | RFC 5256 base-subject extraction and reply/forward classification | conversation identity by itself |
| `collation` | RFC 5051 comparison-key preparation | locale UI collation |
| `dates` | RFC-style Date/INTERNALDATE normalization and ordering key support | mailbox clock or persistence |
| `container` | identity-based thread nodes and safe traversal primitives | protocol formatting |
| `threading` | canonical JWZ/RFC 5256 batch forest construction and ordering stages | mailbox sessions or storage |
| `adapters` | conversion from Python `email` messages into `Message` | transport ownership |
| `imap` | pure projection/serialization to RFC 5256 thread-data | authentication, command parsing, network writes |

PR #20 adds an `incremental` module only on its active branch. That module is target architecture until merged.

## 3. Canonical batch pipeline

```text
caller input
→ adapter / Message validation
→ identifier normalization
→ reference container graph
→ parent linking with cycle prevention
→ dummy pruning / promotion
→ optional RFC 5256 subject merge
→ optional RFC 5256 sent-date ordering
→ Container roots
→ optional pure IMAP projection/serialization
```

The pipeline must be deterministic for equivalent input sequence, Unicode version, options, and mailbox metadata.

## 4. Reference-threading invariants

### TRD-INV-001 Identifier normalization

Message identifiers and header reference identifiers are normalized before graph identity is assigned. Invalid or duplicate identifiers must not create ambiguous shared ownership.

### TRD-INV-002 Reference precedence

A usable `References` chain is authoritative. Only when it is unavailable does the first valid `In-Reply-To` identifier become the fallback parent relation.

### TRD-INV-003 Single parent and cycle safety

A container can have at most one parent. Reparenting must not create a cycle. Traversal of hostile or accidentally cyclic structures must terminate.

### TRD-INV-004 Missing ancestors

Referenced-but-absent messages may be represented by dummy containers, but dummy nodes are structural placeholders only and never invent message payloads.

### TRD-INV-005 Canonical oracle

No adapter, serializer, incremental layer, host integration, or benchmark may maintain a second copy of the threading algorithm. Structural parity is defined against `thread_messages`.

## 5. Subject and Unicode requirements

- Subject fallback is disabled by default.
- Base-subject extraction follows the RFC 5256 ordered normalization procedure, including reply/forward artifacts and mailing-list blobs.
- Comparison uses an RFC 5051-compatible simple titlecase + canonical/compatibility decomposition key.
- The implementation must not use locale-sensitive comparison or treat confusable characters from unrelated scripts as equal.
- Unicode algorithm/version assumptions must be documented and covered by regression examples.

## 6. Sent-date ordering requirements

When enabled:

1. normalize usable `Date` values to aware UTC;
2. treat absent/invalid zones according to the documented RFC-compatible policy;
3. treat invalid time fields according to the documented midnight repair policy;
4. fall back to `INTERNALDATE` when `Date` is unusable;
5. derive a positive effective ordering sequence value from explicit `sequence_number` when supplied, otherwise from the one-based `input_position`; explicit values must be positive and the effective values must be unique across all sorted messages, not only exact date ties;
6. treat `input_position` only as an internal deterministic ordering fallback and never as a public IMAP sequence number;
7. order dummy-root children before deriving the dummy ordering key;
8. apply root/sibling ordering in the RFC-defined stages, including bottom-up ordering after subject merge.

The historical default remains input/first-appearance behavior when ordering is not requested.

## 7. IMAP serialization requirements

The serializer is a pure function over an already-built source forest plus mailbox identifier metadata.

- It must not mutate source `Container` objects.
- Search-result filtering may omit real messages while retaining dummy structure needed to encode descendants.
- Identifier sources may be sequence number, UID, or a caller resolver.
- Identifiers must be non-zero unsigned 32-bit integers and unique within the emitted result.
- Missing UIDs, missing sequence numbers, duplicates, invalid types, booleans-as-integers, and unsafe line endings fail closed.
- The stdlib bulk adapter must not fabricate public mailbox identifiers from iterable order.
- Deep chains and nested sibling structures must serialize iteratively.
- Output framing is exact and deterministic.

## 8. Adapter requirements

`message_from_email` and `thread_email_messages` must preserve source payload ownership while defensively parsing raw identification/reference/subject fields. Unknown character sets and malformed historical encoded-word data must not crash the entire mailbox ingest when a safe literal fallback is available. Bulk iterable position may support internal deterministic sent-date ordering only; a host that needs protocol sequence/UID output supplies that metadata explicitly.

## 9. Active incremental-state target

PR #20 is not as-built protected-main behavior. Its technical contract is retained here to prevent architectural drift during review:

- stable caller-owned message keys, independent of mutable IMAP sequence numbers;
- atomic additions/replacements/removals with optimistic `expected_version`;
- transaction rollback on validation failure;
- affected-component recomputation through the canonical batch oracle;
- explicit component/thread merge and split deltas;
- defensive public forest copies while retaining caller payloads by reference;
- payload-free, versioned, JSON-safe snapshots;
- external RFC 8474 EMAILID/THREADID validation without silent rewrite;
- process-local synchronization only; host owns distributed serialization and persistence;
- bounded small-delta work in default ordering mode, with benchmark evidence rather than unqualified complexity claims.

This target becomes as-built only after the implementing PR lands on protected `main`.

## 10. Performance and resource requirements

- Runtime operations should avoid recursion proportional to mailbox depth.
- No feature may require loading a database, network provider, or LLM.
- The package remains zero-runtime-dependency unless a separately accepted ADR changes the boundary.
- Mailbox-scale claims require reproducible benchmark evidence and parity digest against a full rebuild.
- Performance optimizations must not bypass canonical structural validation.

## 11. Packaging and compatibility

- Python support: 3.10–3.14 on the current protected-main release line.
- The CI matrix must prove every supported Python minor version and the package job must build/hash-install/smoke the wheel under Python 3.14.
- PEP 561 `py.typed` is included in wheels.
- Wheel and source distribution must build from the reviewed dependency lock/toolchain.
- Installed-wheel smoke tests run outside the repository source tree.
- Runtime dependency count remains zero on the current architecture.
- Dependency or Python point-release changes must re-prove the complete support matrix rather than inheriting predecessor-head compatibility evidence.

## 12. Security requirements

Runtime source must not initiate network requests, open databases, spawn shells, consume model credentials, or execute message payloads. Hostile caller objects are bounded by public validation/type contracts at sensitive serialization/snapshot boundaries. See `docs/SECURITY.md` and `docs/THREAT_MODEL.md`.

## 13. Verification requirements

- exact 100% production statement and branch coverage;
- 100% authored production docstrings;
- focused RFC examples plus malformed/deep/cyclic/property-style tests;
- batch/projection non-mutation tests;
- packaging and external-install smoke;
- immutable action/dependency supply-chain verification;
- Python 3.10–3.14 current-head CI evidence;
- exact-current-head GitHub CI, SAST/security, review, and unresolved-thread evidence before merge.

## 14. Integration contract

ThreadWeave exposes typed in-process APIs. A host such as naruon owns tenancy, authentication, persistence, mailbox synchronization, durable optimistic versions, distributed locks, remote APIs, and application-level audit. Hosts must not reach into private ThreadWeave state or persist undocumented internal container identities as stable external identifiers.

## 15. Change-control rule

A change that adds runtime I/O, persistence, a new protocol authority, a second structural oracle, a new Unicode comparison contract, a new durable state format, or a supported Python-version boundary requires an ADR or explicit compatibility decision plus PRD/TRD/Architecture/Test/Security reconciliation in the same change.