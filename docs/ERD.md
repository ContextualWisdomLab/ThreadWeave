# ThreadWeave Conceptual Domain and Evidence Model

**Status:** Accepted conceptual model. ThreadWeave itself persists no database entities.  
**Last reviewed:** 2026-08-09

This document satisfies the repository's ERD/domain-model requirement without inventing persistence the package does not own. Solid entities describe current runtime concepts. Dashed/labelled active-PR concepts describe PR #20 only. Host persistence is external.

## Current conceptual model

```mermaid
erDiagram
    MESSAGE_RECORD ||--o| CONTAINER_NODE : represented_by
    CONTAINER_NODE ||--o{ CONTAINER_NODE : contains
    THREAD_FOREST ||--o{ CONTAINER_NODE : has_root
    MESSAGE_RECORD ||--o{ REFERENCE_EDGE : references
    REFERENCE_EDGE }o--|| MESSAGE_RECORD : resolves_to_when_present
    MESSAGE_RECORD ||--o| MAILBOX_METADATA : may_have
    THREAD_FOREST ||--o{ THREAD_PROJECTION : projects_to
    MAILBOX_METADATA ||--o{ THREAD_PROJECTION : supplies_identifier

    MESSAGE_RECORD {
      string message_id
      string references
      string in_reply_to
      string subject
      datetime sent_date
      datetime internal_date
      any payload_reference
    }

    MAILBOX_METADATA {
      int sequence_number
      int uid
    }

    CONTAINER_NODE {
      string normalized_message_id
      bool is_dummy
      object message_reference
    }

    REFERENCE_EDGE {
      int chain_position
      string normalized_reference_id
    }

    THREAD_FOREST {
      bool group_by_subject
      bool sort_by_sent_date
      string unicode_policy
    }

    THREAD_PROJECTION {
      string identifier_mode
      string include_policy
      string serialized_thread_data
    }
```

These are **conceptual names**, not database table names and not necessarily Python class names. The as-built classes are chiefly `Message` and `Container`; a returned root list constitutes the conceptual `THREAD_FOREST`.

## Runtime ownership

- `MESSAGE_RECORD.payload_reference` is opaque and caller-owned.
- `MAILBOX_METADATA` is supplied by the host; ThreadWeave does not assign mailbox sequence numbers or UIDs.
- Dummy `CONTAINER_NODE` values represent missing ancestors and do not invent a `MESSAGE_RECORD`.
- `THREAD_PROJECTION` is derived output; it is not durable protocol/session state.
- Reference edges are derived from normalized RFC headers and need not be materialized as separate Python objects.

## Host persistence boundary

```mermaid
flowchart LR
    DB[(Host mailbox database)]
    HOST[Host service]
    INPUT[Message + mailbox metadata]
    TW[ThreadWeave]
    FOREST[Thread forest]
    AUDIT[(Host audit / cache, optional)]

    DB --> HOST
    HOST --> INPUT
    INPUT --> TW
    TW --> FOREST
    HOST --> AUDIT
    FOREST -. host chooses to persist/cache .-> AUDIT
```

ThreadWeave does not define the host schema, tenant key, user key, mailbox table, retention policy, or authorization relation. A host may persist its own projection/cache, but it must version that contract independently rather than treating private Python object identity as a durable database identifier.

## Active incremental target — PR #20 only

**Maturity:** ACTIVE-PR / Proposed; PR #20 is **not protected-main as-built behavior**.

```mermaid
erDiagram
    INCREMENTAL_INDEX ||--o{ INDEXED_MESSAGE : contains
    INCREMENTAL_INDEX ||--o{ THREAD_PROJECTION_STATE : caches
    INCREMENTAL_INDEX ||--o{ IDENTITY_ASSOCIATION : tracks
    MAILBOX_CHANGE_SET ||--o{ INDEXED_MESSAGE : adds_or_replaces
    MAILBOX_CHANGE_SET ||--o{ MESSAGE_KEY : removes
    MAILBOX_CHANGE_SET ||--|| THREAD_DELTA : yields
    THREAD_DELTA ||--o{ THREAD_TRANSITION : reports
    INCREMENTAL_INDEX ||--o| SNAPSHOT_ARTIFACT : serializes_to

    INCREMENTAL_INDEX {
      int optimistic_version
      bool group_by_subject
      bool sort_by_sent_date
    }

    INDEXED_MESSAGE {
      string message_key
      object message_reference
      string email_id
      string thread_id
    }

    MESSAGE_KEY {
      string caller_owned_key
    }

    MAILBOX_CHANGE_SET {
      int expected_version
      tuple additions
      tuple replacements
      tuple removals
    }

    THREAD_DELTA {
      int version
      tuple affected_message_keys
      tuple projection_changes
    }

    THREAD_TRANSITION {
      string transition_type
      tuple before_roots
      tuple after_roots
    }

    THREAD_PROJECTION_STATE {
      string root_key
      tuple traversal_message_keys
    }

    IDENTITY_ASSOCIATION {
      string email_id
      string thread_id
      int active_reference_count
    }

    SNAPSHOT_ARTIFACT {
      int schema_version
      json structural_state
    }
```

This second ERD is an **ACTIVE-PR conceptual target**. None of these entities may be described as protected-main persisted state until PR #20 or a successor is merged. Even after merge, the index remains process-local library state unless a separate host persists its documented snapshot.

## Identity rules

- `message_key` in the active target is caller-owned and stable across mutable IMAP sequence-number changes.
- `message_id`, RFC 8474 EMAILID/THREADID, sequence number, UID, and caller `message_key` are different identity domains and must never be conflated.
- Public IMAP sequence numbers and UIDs are validated protocol metadata, not storage primary keys for ThreadWeave.
- Python object identity is used for graph safety but is not a durable external identifier.

## Temporal rules

ThreadWeave is not a psychometric or temporal database, but ordering metadata still has explicit semantics:

- `sent_date` represents message header date evidence;
- `internal_date` is the mailbox fallback ordering value;
- `sequence_number` is a mailbox-position ordering/tie-break input when explicitly supplied; omitted values may use input position only as an internal sort fallback;
- none of these are transaction timestamps or host audit timestamps.

A host that persists snapshots or deltas should record its own transaction/system time and must not overload message dates for that purpose.

## Persistence acceptance rule

If ThreadWeave ever begins owning persistence directly, that is an architectural boundary change. It requires a new Accepted ADR, migration and rollback design, tenant/authorization model, operational/recovery contract, security/threat-model updates, and an as-built physical ERD. Until then, this document remains conceptual.