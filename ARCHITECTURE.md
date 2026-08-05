# ThreadWeave Architecture

## Decision status

This document is the repository-level architecture decision record. `AGENTS.md` is
the canonical operating policy; this file explains component boundaries and data
flow for human reviewers and embedding services such as naruon.

## Architectural goal

ThreadWeave provides one standards-grounded threading kernel that works both as a
zero-runtime-dependency Python package and as a module inside a larger mail or
knowledge platform. Protocol, incremental state, automation, and release concerns
remain separate from the canonical batch algorithm.

## Modules

| Boundary | Responsibility | Must not own |
|---|---|---|
| `headers`, `encoded_words`, `subject`, `collation`, `dates` | RFC parsing, normalization, and comparison primitives | graph state, sockets, databases |
| `threading`, `container` | authoritative JWZ/RFC 5256 batch forest | mailbox sessions, persistence, IMAP framing |
| `incremental` | caller keys, atomic change sets, component indexes, deltas, payload-free snapshots | a second threading algorithm, database/network state |
| `imap` | non-mutating RFC 5256 `THREAD`/`UID THREAD` presentation | authentication, command parsing, mailbox storage |
| stdlib adapters | conversion from Python `email` messages | transport sessions or durable state |
| GitHub workflows and `scripts/ci` | review-first automation, NIM isolation, release evidence | runtime package behavior |

## Authoritative data flow

```text
caller message metadata
  -> RFC normalization
  -> canonical batch thread_messages(component)
  -> Container forest
  -> optional incremental component cache and ThreadDelta
  -> optional IMAP response projection
```

The incremental layer over-approximates connectivity with normalized message IDs,
effective reference IDs, and optional RFC 5051 subject keys. Every affected
component is still evaluated by `thread_messages`; no copy of the threading rules
is maintained in incremental code.

## State and mutation policy

- `IndexedMessage.message_key` is caller-owned and immutable across revisions.
- `apply` validates and computes on isolated transaction state, then commits once.
- Reverse connectivity buckets use copy-on-write mutation.
- Complete root/projection views are lazy caches invalidated by a successful change.
- `roots` returns a defensive structural copy; payload references stay caller-owned.
- Snapshot schema version 1 contains structural metadata only, never payload objects
  or graph pointers.
- RFC 8474 `EMAILID` and `THREADID` remain external identities. Structural merges
  and splits are explicit transitions rather than silent identifier rewrites.

## Ordering and protocol policy

Implicit input positions may be used internally for RFC 5256 sent-date ordering,
but they are not mailbox sequence numbers and are cleared before public roots are
returned. IMAP serialization therefore fails closed unless callers supply valid
sequence numbers or UIDs.

## Scale evidence

The deterministic benchmark runs incremental and full-rebuild workers in separate
processes. It compares projection SHA-256 values and records initial-build time,
delta-application time, full-view materialization time, full-rebuild time, affected
message count, root count, and peak RSS. Scheduled evidence defaults to 100,000
existing messages.

## Integration policy

Naruon and other services should own persistence, tenancy, authentication,
mailbox synchronization, and external stable-ID policy. They pass immutable caller
keys and `Message` metadata into ThreadWeave and consume `ThreadDelta`, snapshots,
or IMAP presentation output through public interfaces.
