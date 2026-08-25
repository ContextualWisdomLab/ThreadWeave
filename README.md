# threadweave

**Standards-grounded JWZ/RFC 5256 email reference threading for Python, with no
runtime dependencies.**

`threadweave` turns a flat iterable of messages into deterministic conversation
trees. It combines the JWZ container model with RFC 5322 identification fields,
RFC 2047 encoded-word decoding, RFC 5256 base-subject extraction and optional
sent-date ordering, RFC 5051 `i;unicode-casemap` comparison, and RFC 5256 IMAP
`THREAD` response serialization, and atomic incremental mailbox updates.

It accepts normalized identifiers, raw header strings, or Python standard-library
`email.message.Message` objects. Malformed historical mail, missing roots,
duplicate identifiers, deep chains, and cyclic references terminate safely.

## Install

```bash
pip install threadweave
```

The wheel includes a PEP 561 `py.typed` marker. The runtime is pure Python
standard library and supports Python 3.10 through 3.14.

## Use from Naruon or another host

ThreadWeave stays independently operable as a stdlib-only package and composable
as a typed library. Naruon is the composition hub and may import this package;
other mail or knowledge services do the same. Hosts call the published API:

```python
from threadweave import thread_messages
```

There is no sibling-checkout or private module path. Install the published
package, then import it. Hosts own authentication, tenancy, mailbox persistence,
and deployment. ThreadWeave owns only in-process threading.

## Reference threading

```python
from threadweave import Message, thread_messages

roots = thread_messages(
    [
        Message(message_id="root@example.com", subject="Deploy plan"),
        Message(
            message_id="reply@example.com",
            references="<root@example.com>",
            in_reply_to="<root@example.com>",
            subject="Re: Deploy plan",
        ),
    ]
)

assert len(roots) == 1
assert roots[0].message.message_id == "root@example.com"
assert [
    node.message.message_id for node in roots[0].iter_descendants()
] == ["reply@example.com"]
```

A valid `References` chain is used in full. When it is unavailable, only the
first valid `In-Reply-To` identifier becomes the parent, as required by RFC 5256.

## Standard-library email adapter

```python
from email import policy
from email.parser import BytesParser

from threadweave import thread_email_messages

messages = [
    BytesParser(policy=policy.default).parsebytes(raw_message)
    for raw_message in raw_messages
]
roots = thread_email_messages(messages)

# Each parsed source object remains available to the caller.
assert roots[0].message.payload is messages[0]
```

The adapter decodes RFC 2047 words under modern and legacy parser policies,
preserves Unicode header text, tolerates unknown character-set labels, and keeps
malformed values instead of aborting the mailbox ingest. `message_from_email`
also accepts mailbox sequence-number and UID metadata for protocol output.

## Subject fallback

Subject grouping is optional because unrelated conversations can legitimately
share a subject.

```python
from threadweave import (
    is_reply_or_forward_subject,
    normalize_subject,
    thread_messages,
    unicode_casemap_key,
)

assert normalize_subject("[project] Re: [fwd: Release plan (fwd)]") == (
    "Release plan"
)
assert is_reply_or_forward_subject("Fwd: Release plan")
assert unicode_casemap_key("Ｔｏｐｉｃ") == unicode_casemap_key("Topic")
assert unicode_casemap_key("é") == unicode_casemap_key("e\u0301")

roots = thread_messages(messages, group_by_subject=True)
```

The RFC 5051 key remains locale-independent and does not collapse visual
confusables from unrelated scripts.

## RFC 5256 sent-date ordering

The historical default remains first-appearance order. Enable RFC ordering
explicitly when mailbox metadata is available:

```python
from threadweave import Message, thread_messages

roots = thread_messages(
    [
        Message(
            message_id="later@example.com",
            sent_date="2 Jan 2026 00:00:00 +0000",
            sequence_number=2,
        ),
        Message(
            message_id="earlier@example.com",
            sent_date="1 Jan 2026 09:00:00 +0900",
            internal_date="1 Jan 2026 00:00:00 +0000",
            sequence_number=1,
        ),
    ],
    sort_by_sent_date=True,
)

assert [root.message.message_id for root in roots] == [
    "earlier@example.com",
    "later@example.com",
]
```

`Date` is normalized to UTC. Invalid or absent zones become UTC, invalid times
become local midnight, unusable values fall back to `INTERNALDATE`, and exact
ties use a unique positive mailbox sequence number. Dummy roots and every
sibling set are sorted in the RFC-defined stages.

## IMAP THREAD response serialization

The core tree remains transport-neutral. IMAP servers and gateways can project a
search result and serialize it into the exact RFC 5256 response shape:

```python
from threadweave import Message, serialize_thread_response, thread_messages

roots = thread_messages(
    [
        Message(message_id="root", sequence_number=3, uid=103),
        Message(
            message_id="child",
            references=["root"],
            sequence_number=6,
            uid=106,
        ),
    ]
)

assert serialize_thread_response(roots) == "* THREAD (3 6)\r\n"
assert serialize_thread_response(roots, identifier="uid") == (
    "* THREAD (103 106)\r\n"
)
```

`serialize_thread_data` also accepts an `include` predicate for the server's
search result and a callable identifier resolver for mailbox metadata stored
outside `Message`. Excluded ancestors are projected as RFC dummy structure;
source containers are never mutated. Cycles, shared nodes, duplicate numbers,
missing UIDs, values outside the non-zero unsigned 32-bit range, and unsafe line
endings fail closed. Both deep chains and nested splits are rendered iteratively.

## Incremental mailbox updates

`IncrementalThreadIndex` applies atomic additions, replacements, and removals
without re-threading unrelated reference components. Caller-owned message keys
remain stable across expunge or mailbox sequence-number changes; optional RFC
8474 `EMAILID` and `THREADID` values are validated and never silently rewritten.

```python
from threadweave import (
    IncrementalThreadIndex,
    IndexedMessage,
    MailboxChangeSet,
    Message,
)

index = IncrementalThreadIndex()
delta = index.apply(
    MailboxChangeSet(
        expected_version=0,
        additions=(
            IndexedMessage(
                "mailbox:101",
                Message(message_id="root", sequence_number=1, uid=101),
                email_id="Email_101",
                thread_id="Thread_7",
            ),
            IndexedMessage(
                "mailbox:102",
                Message(
                    message_id="reply",
                    references=["root"],
                    sequence_number=2,
                    uid=102,
                ),
                email_id="Email_102",
                thread_id="Thread_7",
            ),
        ),
    )
)

assert delta.version == 1
assert index.projections[0].message_keys == ("mailbox:101", "mailbox:102")
assert IncrementalThreadIndex.restore(index.snapshot()).projections == (
    index.projections
)
```

Every affected component is recomputed through the canonical batch threader, and
full-rebuild parity is the correctness oracle. Default-mode transactions stage
records, positions, connectivity, component ownership, and RFC 8474 identity
changes through bounded overlays; they do not copy or iterate unrelated mailbox
state before one validated commit. Structural merges and splits are reported
explicitly. `roots` returns a defensive structural copy, so callers may
traverse or edit that graph without corrupting reusable index state; payload objects
remain caller-owned references. Internal sent-date tie-break positions never become
public IMAP sequence numbers. Versioned snapshots omit arbitrary payloads, reject
unknown, malformed, cyclic, aliased, or oversized input, and count UTF-8
code-point width to stop at the configured byte limit without encoding a second
full bytes copy. Restore checks the fixed root schema and record-count bound before
nested traversal, then caps the structural scan with the same byte limit. See
[`docs/incremental-threading.md`](docs/incremental-threading.md) for the atomicity,
identity, snapshot, complexity, and RFC boundaries.

## Public API

| Symbol | Purpose |
|---|---|
| `Message` | Thread input plus payload and optional mailbox ordering/protocol metadata. |
| `Container` | Identity-based, loop-safe thread-tree node. |
| `thread_messages(...)` | Build JWZ/RFC 5256 thread roots from any iterable. |
| `message_from_email(...)` | Convert one stdlib email object. |
| `thread_email_messages(...)` | Convert and thread stdlib email objects. |
| `IncrementalThreadIndex` | Apply atomic mailbox deltas and expose batch-equivalent roots. |
| `IndexedMessage` | Bind one stable caller key and optional RFC 8474 identities to a message. |
| `MailboxChangeSet` | Describe one optimistic additions/replacements/removals transaction. |
| `ThreadDelta` | Report affected keys, projection changes, merges, and splits. |
| `ThreadProjection` | Describe one root with traversal-ordered caller keys and THREADIDs. |
| `serialize_thread_data(...)` | Render RFC 5256 `thread-data` without response framing. |
| `serialize_thread_response(...)` | Render one untagged `* THREAD` response. |
| `ThreadSerializationError` | Report invalid graph or mailbox identifier state. |
| `IdentifierResolver` | Select sequence-number, UID, or callable identifier output. |
| `MessageFilter` | Type alias for a server search-result predicate. |
| `normalize_message_id` | Normalize one RFC 5322 identifier. |
| `extract_reference_ids` | Parse and deduplicate a reference header. |
| `generate_email_fingerprint` | Produce a deterministic SHA-256 identity fallback. |
| `decode_header_text` | Decode RFC 2047 header text defensively. |
| `normalize_subject` | Extract the RFC 5256 base subject. |
| `is_reply_or_forward_subject` | Classify RFC reply/forward artifacts. |
| `is_reply_subject` | Compatibility alias for the standardized classifier. |
| `unicode_casemap_key` | Prepare an RFC 5051 comparison key. |
| `DateValue` | Accepted date input: `datetime`, RFC-style text, or `None`. |
| `normalize_sent_date` | Normalize `Date` and `INTERNALDATE` to aware UTC. |

## Quality contract

- Production statement and branch coverage are required to remain at **100%**.
- Every authored production module and callable must have a docstring.
- CI runs Ruff, compileall, doctests, pytest with coverage, and dependency checks
  on Python 3.10, 3.11, 3.12, 3.13, and 3.14.
- CI builds wheel and source distributions, verifies `py.typed`, installs the
  wheel outside the source tree, and executes a smoke test.
- Graph operations, IMAP rendering, and incremental component traversal are
  iterative and identity-guarded; deep or cyclic malformed input cannot recurse
  indefinitely.
- `benchmarks/incremental_mailbox.py` compares isolated incremental and full
  rebuild processes at 100,000 messages, verifies an identical projection digest,
  and records affected-message count, wall time, delta retained/transient traced
  bytes, and peak RSS as JSON evidence.

## Reproducible CI supply chain

ThreadWeave keeps its runtime dependency-free, but treats test and build tools as
executable supply-chain inputs. `requirements/ci.in` records exact direct intent;
a pinned uv compiler generates the universal `requirements/ci.lock` with
transitive SHA-256 hashes for Python 3.10-3.14. CI regenerates the lock and
requires a byte-for-byte match before installing it with pip hash-checking mode.
Builds run without isolation because the reviewed Hatchling backend is already
installed from that lock. See [`docs/supply-chain.md`](docs/supply-chain.md) for
the refresh procedure, reviewer checklist, and rollback contract.

## Architecture and standards boundary

The package remains useful both as a standalone dependency and as a module in
`naruon` or another service. The batch-threading, incremental-index, subject,
collation, and date layers are transport-neutral. IMAP `THREAD` response
serialization is a separate presentation layer rather than protocol state
embedded in the core model.

See [`docs/research`](docs/research/README.md) for JWZ, RFC 5322, RFC 2047,
RFC 5051, RFC 5256, RFC 6532, RFC 7162, RFC 8474, RFC 8621, RFC 9051,
Unicode-version boundaries, and PEP 561.

Hourly autonomous maintenance is documented in
[`docs/operations/hourly-autonomous-maintenance.md`](docs/operations/hourly-autonomous-maintenance.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
