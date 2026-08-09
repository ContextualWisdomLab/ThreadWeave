# ThreadWeave UML and Runtime Views

**Status:** Accepted diagrams for protected-main behavior plus explicitly labelled active-PR target views.  
**Last reviewed:** 2026-08-09

## Package/component view

```mermaid
flowchart TB
    subgraph input[Input and normalization]
        AD[adapters]
        HD[headers]
        EW[encoded_words]
    end
    subgraph policy[Comparison and ordering]
        SJ[subject]
        CO[collation]
        DT[dates]
    end
    subgraph core[Canonical threading]
        TH[threading]
        CN[container]
    end
    subgraph presentation[Presentation]
        IM[imap]
    end

    AD --> HD
    AD --> EW
    AD --> TH
    TH --> HD
    TH --> SJ
    SJ --> CO
    TH --> DT
    TH --> CN
    CN --> IM
```

## Batch threading sequence

```mermaid
sequenceDiagram
    actor Caller
    participant Adapter as adapter/Message
    participant Headers as headers
    participant Threader as thread_messages
    participant Subject as subject/collation
    participant Dates as dates
    participant Forest as Container forest

    Caller->>Adapter: messages + options
    Adapter->>Headers: normalize IDs/references
    Headers-->>Threader: normalized identities
    Threader->>Threader: create containers and placeholders
    Threader->>Threader: link references with cycle guard
    Threader->>Threader: prune/promote dummy nodes
    opt group_by_subject
        Threader->>Subject: normalize and compare base subjects
        Subject-->>Threader: grouping keys / reply-forward class
        Threader->>Threader: merge eligible roots
    end
    opt sort_by_sent_date
        Threader->>Dates: normalize Date / INTERNALDATE
        Dates-->>Threader: ordering keys
        Threader->>Threader: RFC ordering stages
    end
    Threader-->>Forest: deterministic roots
    Forest-->>Caller: caller-owned payload references preserved
```

## Sent-date ordering sequence

```mermaid
sequenceDiagram
    participant T as threading
    participant D as dates
    participant R as root/sibling sets

    T->>D: Date, INTERNALDATE, sequence_number
    D->>D: parse and normalize to aware UTC
    alt Date unusable
        D->>D: fall back to INTERNALDATE
    end
    D-->>T: normalized date key
    T->>R: sort dummy-root children
    T->>R: derive dummy key from first child
    T->>R: sort top-level siblings
    T->>R: optional subject grouping
    T->>R: sort remaining sibling sets bottom-up
    R-->>T: RFC-compatible ordered forest
```

## IMAP projection sequence

```mermaid
sequenceDiagram
    actor Host
    participant Forest as source Container forest
    participant IMAP as imap serializer
    participant Projection as projected thread-data

    Host->>IMAP: roots + identifier mode/resolver + optional include predicate
    IMAP->>Forest: traverse without mutation
    IMAP->>IMAP: validate cycle/shared-node state
    IMAP->>IMAP: retain dummy ancestry for included descendants
    IMAP->>IMAP: resolve and validate sequence/UID identifiers
    IMAP->>Projection: iterative thread-data rendering
    Projection-->>Host: thread-data or * THREAD response
```

## Batch object/class view

```mermaid
classDiagram
    class Message {
      +message_id
      +references
      +in_reply_to
      +subject
      +sent_date
      +internal_date
      +sequence_number
      +uid
      +payload
    }
    class Container {
      +message
      +parent
      +children
      +iter_descendants()
    }
    class ThreadForest {
      <<conceptual>>
      +roots[]
    }
    class IdentifierResolver {
      <<protocol port>>
    }
    class ThreadResponse {
      <<serialized value>>
    }

    Message "0..1" <-- "1" Container : carries
    Container "0..*" --> "0..1" Container : parent
    ThreadForest o-- Container : roots
    ThreadForest --> IdentifierResolver : projected by
    IdentifierResolver --> ThreadResponse : renders
```

`ThreadForest` and `ThreadResponse` are conceptual documentation names, not additional persisted/runtime classes.

## Authority view

```mermaid
flowchart LR
    HOST[Host application]
    META[mailbox metadata]
    TW[ThreadWeave runtime]
    DB[(host persistence)]
    AUTH[host auth / tenancy]
    OUT[thread forest or RFC output]

    AUTH --> HOST
    DB --> HOST
    META --> HOST
    HOST -->|typed values only| TW
    TW --> OUT
```

ThreadWeave has no authority to query the host database, authenticate a user, assign tenant ownership, or send network responses by itself.

## Active incremental state view — PR #20 target, not protected-main

```mermaid
stateDiagram-v2
    [*] --> version_n
    version_n --> validating_change: apply(change, expected_version=n)
    validating_change --> rejected: invalid/duplicate/conflicting change
    validating_change --> recomputing: validated affected components
    recomputing --> committing: batch-oracle parity succeeds
    recomputing --> rejected: structural validation fails
    committing --> version_n_plus_1: atomic publish
    version_n_plus_1 --> [*]
    rejected --> version_n: no partial mutation
```

```mermaid
sequenceDiagram
    actor Host
    participant Index as IncrementalThreadIndex
    participant Batch as canonical thread_messages

    Host->>Index: MailboxChangeSet(expected_version)
    Index->>Index: validate keys/identity/version
    Index->>Index: derive affected components
    Index->>Batch: rebuild affected component(s)
    Batch-->>Index: canonical roots
    Index->>Index: compute projection merge/split delta
    Index->>Index: atomic commit or rollback
    Index-->>Host: ThreadDelta + new version
```

These diagrams become as-built only if PR #20 merges. Until then they describe the active design under review.

## Deployment view

```mermaid
flowchart TB
    subgraph library[Current deployment]
        HOSTAPP[Host Python process]
        PKG[threadweave package]
        HOSTAPP --> PKG
    end

    subgraph wrapped[Optional external wrapper owned elsewhere]
        API[Service/API layer]
        AUTHZ[tenant/auth/rate/audit]
        STORE[(mailbox store)]
        API --> AUTHZ
        API --> STORE
        API --> PKG2[threadweave package]
    end
```

No database or service deployment is required to use the package.

## Maintenance rule

Update these views when module ownership, public lifecycle, protocol authority, durable state, automation authority, or deployment responsibility changes. Never move an ACTIVE-PR feature into the as-built diagrams until it is present on protected `main`.