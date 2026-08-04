# Incremental Thread Index Design

## Status

Approved product direction for issue #19. This design is implemented on a feature
branch while release blocker #17 keeps the `0.2.0` source on `main` frozen. The
feature must remain draft and must not merge until the `0.2.0` release succeeds.

## Product problem

`thread_messages` is a deterministic and standards-grounded batch operation, but
mail servers, migration products, archive viewers, and naruon-style control planes
receive mailbox deltas. Rebuilding an unrelated million-message mailbox after every
arrival, expunge, or metadata correction wastes CPU and memory and gives integrators
no explicit stable-identity handoff.

## Goals

1. Accept additions, replacements, and removals as one atomic change set.
2. Use an immutable caller-owned message key that is independent of IMAP sequence
   numbers and UIDs.
3. Recompute only the old components and newly connected buckets touched by a
   change while preserving exact parity with a full `thread_messages` rebuild.
4. Expose deterministic thread projections and explicit merge/split transitions.
5. Carry optional caller-owned RFC 8474 `EMAILID` and `THREADID` metadata without
   silently changing a reported identifier.
6. Snapshot and restore versioned JSON-safe state without serializing payloads.
7. Preserve zero runtime dependencies, Python 3.10-3.13 support, iterative graph
   processing, complete docstrings, and 100% statement and branch coverage.

## Non-goals for this slice

- Implementing an IMAP, JMAP, database, socket, authentication, or tenant layer.
- Inventing a server-owned stable `THREADID` policy.
- Persisting arbitrary caller payloads.
- Replacing `thread_messages`; the batch function remains the correctness oracle.
- Claiming sublinear behavior for an initial build or snapshot restore. The bounded
  update path, not construction or restore, carries the incremental requirement.

## Public API

### `IndexedMessage`

A frozen record containing:

- `message_key: str`: immutable caller-owned key.
- `message: Message`: message metadata; the index copies structural fields on entry.
- `email_id: str | None`: optional caller-owned RFC 8474 immutable content ID.
- `thread_id: str | None`: optional caller-owned RFC 8474 thread correlator.

Payload objects remain caller-owned and are retained only in memory. They never enter
snapshots or equality/delta calculations.

### `MailboxChangeSet`

A frozen atomic request containing:

- `expected_version: int`
- `additions: tuple[IndexedMessage, ...]`
- `replacements: tuple[IndexedMessage, ...]`
- `removals: tuple[str, ...]`

The three key sets must be disjoint. Additions require absent keys; replacements and
removals require existing keys. Any failure leaves the index unchanged.

### `ThreadProjection`

A frozen, JSON-safe description of one returned thread root:

- `message_keys`: traversal-ordered caller keys.
- `thread_ids`: sorted distinct external thread IDs represented by the root.

### `ThreadDelta`

A deterministic result containing previous/new versions, affected message keys,
added/removed/updated projections, and explicit merge/split external-ID groups.
Structural overlap is computed from caller keys; mutable IMAP sequence numbers never
serve as identity.

### `IncrementalThreadIndex`

Constructor options mirror the batch API:

- `group_by_subject: bool = False`
- `sort_by_sent_date: bool = False`
- `max_snapshot_records: int = 1_000_000`
- `max_snapshot_bytes: int = 256 * 1024 * 1024`

Methods and properties:

- `apply(change_set) -> ThreadDelta`
- `roots -> tuple[Container, ...]`
- `projections -> tuple[ThreadProjection, ...]`
- `version -> int`
- `snapshot() -> dict[str, object]`
- `restore(snapshot, *, max_snapshot_records=..., max_snapshot_bytes=...)`

## Incremental algorithm

The index keeps four kinds of state:

1. Ordered records and stable insertion positions.
2. Per-message connectivity tokens.
3. Reverse token buckets.
4. Component membership and component-local `thread_messages` output.

A record contributes tokens for its normalized `Message-ID`, every effective RFC
5256 reference identifier, and—when subject grouping is enabled—its RFC 5051 base
subject key. Token connectivity deliberately over-approximates the final root graph;
that can recompute a larger component but cannot omit a dependency.

For one change set:

1. Validate version, key ownership, immutable external IDs, numeric metadata, and
   JSON-safe identifier bounds without mutating state.
2. Seed the affected set with every old component containing a replaced/removed key.
3. Remove old token memberships and insert new memberships on copied indexes.
4. Add every component touching an old or new token, including bridge additions.
5. Expand only that candidate region through current token buckets.
6. Repartition the candidate region iteratively and invoke `thread_messages` for
   each new component in global insertion order.
7. Reuse untouched component roots and compose the global root list. Default output
   uses first insertion position; RFC sent-date mode uses the same UTC/date,
   sequence-number, and input-position ordering contract as the batch API.
8. Compare before/after projections and commit copied state only after all steps
   succeed.

Removing an internal or root message seeds its entire old component, so a split is
fully rediscovered. Adding a bridge message includes every touched old component, so
merges are explicit. Unrelated components are neither passed to `thread_messages`
nor traversed during the update.

## External identity rules

- Message keys never change; replacement uses the same key.
- A non-null `email_id` or `thread_id` cannot be removed or changed by replacement.
- All records sharing one non-null `email_id` must expose the same non-null
  `thread_id`, matching RFC 8474.
- Structurally merged roots retain every caller thread ID and emit a merge group.
- Structural splits emit a split group rather than silently rewriting IDs.
- The core does not choose a canonical external ID. A server-specific policy may
  consume the explicit transition later.

## Snapshot contract

Snapshot schema version `1` contains options, optimistic version, ordered records,
message metadata, and optional external IDs. It excludes payloads and derived graph
state. References are stored as normalized identifier lists. Datetimes are encoded
as tagged ISO 8601 strings; textual date inputs remain textual.

Restore rejects unknown schema versions, duplicate or malformed keys, unexpected
fields, non-finite/boolean numeric metadata, oversized records/documents, and invalid
external-ID invariants. It rebuilds derived indexes through the same public
validation path and compares no untrusted serialized graph pointers.

## Error model

- `IncrementalThreadError`: invalid change or snapshot.
- `VersionConflictError`: optimistic version mismatch.
- `ExternalIdentityError`: immutable/cross-record EMAILID or THREADID violation.

Messages are bounded and do not include payload representations, local paths, or
secrets.

## Verification

Required tests include:

- additions, replacement, removal, delayed ancestor, bridge merge, and component
  split against a complete batch rebuild;
- duplicate/missing Message-ID, raw headers, Unicode subjects, date sorting, UID
  output, and RFC 5256 serialization parity;
- explicit merge/split external-ID transitions and RFC 8474 invariants;
- atomic rollback and optimistic version conflict;
- deterministic snapshot round trip, payload omission, malformed/oversized input,
  and idempotency through version conflicts;
- a spy proving an unrelated component is not passed to `thread_messages` during a
  bounded update;
- deep and hostile metadata cases without recursion;
- installed-wheel public API smoke coverage.

A scheduled/manual benchmark follows in a separate bounded PR with at least 100,000
messages, bounded deltas, wall time, peak RSS, affected-message count, and full
rebuild comparison.

## References

Gondwana, B. (2018). *IMAP extension for object identifiers* (RFC 8474). RFC
Editor. https://doi.org/10.17487/RFC8474

Jenkins, N., & Newman, C. (2019). *The JSON Meta Application Protocol (JMAP) for
mail* (RFC 8621). RFC Editor. https://doi.org/10.17487/RFC8621

Melnikov, A., & Cridland, D. (2014). *IMAP extensions: Quick flag changes
resynchronization (CONDSTORE) and quick mailbox resynchronization (QRESYNC)*
(RFC 7162). RFC Editor. https://doi.org/10.17487/RFC7162

Melnikov, A., & Leiba, B. (Eds.). (2021). *Internet Message Access Protocol
(IMAP)—Version 4rev2* (RFC 9051). RFC Editor.
https://doi.org/10.17487/RFC9051
