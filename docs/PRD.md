# ThreadWeave Product Requirements Document

**Status:** Accepted baseline for protected `main` at `8af58f141dba00c7251c0ff4a5f7baf4563c8ebd`  
**Product version represented:** `0.2.0`  
**Last reviewed:** 2026-08-10

## 1. Product purpose

ThreadWeave is a zero-runtime-dependency Python library for deterministic, standards-grounded email conversation threading. It turns normalized messages, raw RFC headers, or Python standard-library email objects into a reusable thread forest and can project that forest into RFC 5256 IMAP `THREAD` or `UID THREAD` response data.

The product exists so mail servers, migration systems, archive/search products, and CWL services such as naruon do not need to reimplement fragile reference-threading, subject normalization, Unicode collation, sent-date ordering, and IMAP presentation rules independently.

## 2. Current protected-main capabilities

The following are implemented on protected `main` and are therefore product claims:

- JWZ-style container construction with RFC 5256 reference-threading semantics;
- RFC 5322 Message-ID normalization and multi-ID `References`/`In-Reply-To` parsing;
- standard-library `email.message.Message` / `EmailMessage` adapters;
- defensive RFC 2047 header decoding;
- RFC 5256 base-subject extraction and optional subject fallback grouping;
- RFC 5051 `i;unicode-casemap` comparison keys;
- optional RFC 5256 sent-date ordering with UTC normalization, `INTERNALDATE` fallback, mailbox-sequence tie-breaking, dummy-root handling, and bottom-up sibling ordering;
- transport-neutral tree model plus exact RFC 5256 `thread-data` / `* THREAD` serialization;
- sequence-number, UID, predicate-based search-result projection, and callable identifier resolution;
- explicit separation between internal iterable-position ordering fallback and host-authoritative public IMAP sequence/UID metadata;
- iterative graph traversal and fail-closed handling of cycles, shared nodes, duplicate/missing/out-of-range protocol identifiers, malformed historical headers, and deep chains;
- PEP 561 `py.typed` packaging and Python 3.10–3.13 support on protected main;
- 100% production statement and branch coverage and authored public docstrings as a merge/release contract.

Python 3.14 compatibility exists on active PR #27 and is not a protected-main claim until that PR integrates.

## 3. Active but not protected-main capability

PR #20 (`feature/incremental-thread-index`) is an **ACTIVE-PR target**, not a current product claim. It proposes an `IncrementalThreadIndex` that applies atomic mailbox additions, replacements, and removals using stable caller keys while delegating affected-component reconstruction to the canonical batch threader. Until that PR is merged, public documentation must label incremental indexing, RFC 8474 identity handoff, payload-free snapshots, and incremental benchmark claims as active-PR behavior.

## 4. Primary users

### Mail server / gateway engineer

Needs exact, deterministic thread structure and RFC presentation without embedding mailbox session, authentication, persistence, or network concerns into the library.

### Migration / archive engineer

Needs tolerant ingestion of malformed historical headers, stable behavior on deep/cyclic reference graphs, and reproducible outputs across runs.

### CWL service integrator

Needs a standalone library that can also be consumed as a module by naruon or another service without hidden database or provider coupling.

## 5. Functional requirements

### PRD-FR-001 Reference threading

The library SHALL use valid `References` chains in full. When a usable `References` chain is unavailable, it SHALL use only the first valid `In-Reply-To` identifier as the fallback parent relation.

### PRD-FR-002 Dummy containers and pruning

The library SHALL represent missing ancestors without inventing message payloads and SHALL prune/promote dummy containers according to the canonical threading algorithm while preventing loops and shared-parent corruption.

### PRD-FR-003 Subject normalization

When subject grouping is enabled, the library SHALL implement the RFC 5256 base-subject procedure and SHALL distinguish reply/forward artifacts from the base subject. Subject grouping MUST remain optional because equal subjects do not prove conversational identity.

### PRD-FR-004 Internationalized comparison

Subject comparison SHALL use an RFC 5051-compatible Unicode casemap key rather than Python locale behavior or unrestricted full special casing. Visually confusable characters from different scripts MUST NOT be collapsed merely because they look alike.

### PRD-FR-005 Sent-date ordering

When `sort_by_sent_date=True`, the library SHALL normalize valid dates to aware UTC, apply documented RFC-compatible repair/fallback rules, and use `INTERNALDATE` when necessary. Each message SHALL have a unique positive **effective ordering sequence value**: an explicit positive mailbox `sequence_number` when supplied, otherwise the one-based input position as an internal fallback. Effective values are validated for uniqueness across all messages participating in sent-date ordering, not only date ties. The input-position fallback MUST NOT be exposed as or treated as a public IMAP sequence number. Historical first-appearance order SHALL remain the default for backward compatibility.

### PRD-FR-006 IMAP projection

The library SHALL serialize valid source trees to RFC 5256 `thread-data` and untagged `* THREAD` responses without mutating the source forest. Search-result filtering SHALL preserve necessary dummy structure. Sequence and UID output SHALL fail closed on invalid or missing identifiers rather than inventing host metadata.

### PRD-FR-007 Standard-library adapter and mailbox authority

The package SHALL accept Python standard-library email objects without forcing callers to manually normalize `References`, `In-Reply-To`, encoded words, or payload ownership. `thread_email_messages(...)` SHALL NOT turn iterable position into public mailbox sequence or UID metadata. Iterable position may be used only by the canonical threader as an internal deterministic ordering fallback. A caller that requires public sequence-number or UID serialization SHALL supply those host-owned identifiers explicitly through `message_from_email(...)` or a serializer identifier resolver.

### PRD-FR-008 Determinism

Equivalent inputs, options, Unicode version, and mailbox metadata SHALL produce equivalent ordered structural outputs independent of hash-map iteration or locale state.

### PRD-FR-009 Incremental target

The active incremental design SHALL preserve the batch threader as the structural correctness oracle, use optimistic versioning for atomic changes, expose explicit merge/split transitions, and avoid silently rewriting externally supplied RFC 8474 identities. This requirement becomes a protected-main product requirement only after the implementing PR merges.

## 6. Safety and trust requirements

- Runtime code SHALL have no network, database, shell, credential, or remote-code execution capability.
- Arbitrary caller payloads SHALL remain caller-owned and MUST NOT be serialized into structural snapshots or protocol output unless a specific public API explicitly owns that transformation.
- Traversal SHALL be iterative or identity-guarded such that hostile cyclic/deep graphs cannot recurse indefinitely.
- Protocol serializers SHALL reject CR/LF-unsafe, missing, duplicate, or out-of-range identifiers rather than normalizing or inventing different values.
- Automated development and release workflows SHALL keep model credentials separated from repository-controlled code and SHALL not allow the development model to approve, merge, tag, or publish its own change.

See `docs/SECURITY.md` and `docs/THREAT_MODEL.md`.

## 7. Quality requirements

- production statement coverage: exactly 100%;
- production branch coverage: exactly 100%;
- authored production module/callable docstrings: 100%;
- Ruff, compileall, doctests, pytest, packaging, wheel-outside-source smoke, and dependency integrity gates;
- real deep-chain, cycle/shared-node, malformed-header, date-ordering, IMAP serialization, adapter-authority, and Unicode regression tests;
- no skipped required gate may count as passing;
- exact current-head GitHub evidence is required before merge/release.

## 8. Non-goals

ThreadWeave does not own:

- IMAP authentication, command parsing, sessions, mailboxes, persistence, distributed locking, or storage;
- message-body semantic classification, embeddings, summarization, or LLM interpretation;
- SMTP delivery;
- anti-spam/phishing judgments;
- arbitrary locale-specific collation beyond the adopted protocol algorithm;
- guaranteed conversational identity from subject equality alone.

## 9. Integration requirements

Standalone use is mandatory. Optional CWL integrations MUST use public typed interfaces and degrade to ordinary library operation when unavailable. Host services own tenancy, authorization, durable versions, mailbox synchronization, distributed write serialization, public sequence/UID lifecycle, and external stable-ID lifecycle.

## 10. Release acceptance

A release candidate is acceptable only from an integrated protected head with all required current-head CI/security/review gates passing, package artifacts freshly built and installed outside the source tree, supply-chain lock/provenance evidence verified, CHANGELOG/version/tag consistency proven, and rollback/recovery procedure reviewed. A successful local suite does not substitute for required GitHub evidence.

## 11. Buyer-visible roadmap

1. complete the `0.2.0` Trusted Publishing prerequisite and verify the public artifact;
2. land and validate the bounded incremental mailbox state boundary after that release prerequisite is satisfied;
3. expose stable adapter guidance for naruon/JMAP/IMAP hosts without importing host persistence into the core;
4. keep mailbox-scale parity/performance evidence reproducible and versioned;
5. add only standards-backed protocol projections that preserve the transport-neutral threading kernel.

## 12. Standards baseline

The normative/research bibliography is maintained under `docs/research/`. Product decisions materially rely on JWZ threading behavior and RFC 2047, RFC 5051, RFC 5256, RFC 5322, RFC 6532, RFC 7162, RFC 8474, RFC 8621, and RFC 9051 where applicable. References are recorded in APA 7 style in the research documentation.