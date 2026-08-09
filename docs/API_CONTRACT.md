# ThreadWeave Public API and Version Contract

**Status:** Accepted for protected `main`  
**Version line:** `0.2.x`  
**Last reviewed:** 2026-08-09

## Contract philosophy

ThreadWeave is an in-process Python library. Its public contract is the exported Python API plus deterministic protocol text returned by RFC serializers. It does not define an HTTP service, database schema, event bus, or authentication protocol.

## Current public surface families

### Message and forest construction

- `Message`
- `Container`
- `thread_messages(...)`
- `message_from_email(...)`
- `thread_email_messages(...)`

Callers own payload objects. The threader owns structural `Container` objects returned for a call.

### Header/subject/date primitives

- `normalize_message_id`
- `extract_reference_ids`
- `generate_email_fingerprint`
- `decode_header_text`
- `normalize_subject`
- `is_reply_or_forward_subject`
- `is_reply_subject` compatibility alias
- `unicode_casemap_key`
- `DateValue`
- `normalize_sent_date`

These functions are deterministic for the documented runtime/Unicode version and input.

### IMAP presentation

- `serialize_thread_data(...)`
- `serialize_thread_response(...)`
- `ThreadSerializationError`
- `IdentifierResolver`
- `MessageFilter`

The serializer accepts an already-built forest and must not mutate it. Default identifiers are mailbox sequence numbers; `identifier="uid"` selects UID output; a callable resolver may supply host-owned metadata. The output is RFC framing text, not a socket write.

## Input compatibility

Reference identifiers may be provided through normalized values or supported raw header text. Standard-library email adapters accept Python email objects and preserve the original object in the caller payload path. Message ordering/serialization metadata remains optional unless an explicitly requested operation needs it.

## Error contract

Public APIs use deterministic exceptions appropriate to their boundary. Callers must not infer success from partial output. Protocol serialization rejects invalid graph/identifier state rather than coercing values. No public exception message should be treated as a stable machine-readable identifier unless its type/API explicitly documents that guarantee.

## Ordering compatibility

`group_by_subject` and `sort_by_sent_date` are explicit behavioral options. Existing default behavior remains reference threading with historical first-appearance ordering. A future change to an option default is compatibility-significant and requires version/migration documentation.

## Protocol serialization contract

- Successful response framing ends with exactly `\r\n` where the public response API specifies it.
- Identifiers are non-zero unsigned 32-bit integers and unique in one projected response.
- Booleans do not satisfy integer identifier requirements.
- Search-result filtering retains structural dummy grouping required to represent included descendants.
- Source containers are not modified.

## Active incremental API target

PR #20 proposes public symbols such as `IncrementalThreadIndex`, `IndexedMessage`, `MailboxChangeSet`, `ThreadDelta`, and `ThreadProjection`. Those names and snapshot schema are **not protected-main API** until merged. Consumers must not depend on them from the released mainline solely because this repository documents the active target.

If accepted, the snapshot must carry an explicit integer schema version and reject unknown versions. Snapshot schema versioning is independent from Python package SemVer.

## Semantic versioning

The package follows Semantic Versioning intent:

- patch: bug/security fixes that preserve documented public behavior;
- minor: backward-compatible public functionality;
- major: incompatible public symbol, default, serialized-format, or required-metadata change.

Because protocol conformance fixes can reveal previously tolerated invalid inputs, release notes must explicitly call out fail-closed behavior changes even when they are semantically patch-level bug fixes.

## Deprecation

Public aliases or behaviors should be deprecated before removal when feasible. Deprecation must state replacement, removal horizon, and compatibility impact. Deprecated paths still require tests until removal.

## No hidden service contract

Naruon, an IMAP service, or another wrapper may expose ThreadWeave over HTTP/RPC, but that external contract belongs to the host repository. Hosts should map ThreadWeave inputs/outputs through a typed adapter and must not expose private module objects as a remote persistence protocol.

## Contract verification

Public API changes require:

- exact focused and full test coverage;
- README/API document synchronization;
- package build and outside-source smoke;
- CHANGELOG entry;
- relevant ADR update when identity, ordering, serialization, persistence, or authority semantics move.