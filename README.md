# threadweave

**Standards-grounded JWZ/RFC 5256 email threading and IMAP `THREAD` response
serialization for Python — pure stdlib, zero runtime dependencies.**

`threadweave` turns a flat iterable of messages into deterministic conversation
trees. It implements the JWZ container model, RFC 5256 `REFERENCES` semantics,
RFC 5322 identification fields, resilient RFC 2047 decoding, exact RFC 5256
base-subject extraction, RFC 5051 `i;unicode-casemap`, opt-in RFC sent-date
ordering, and compact `THREAD` / UID `THREAD` response serialization.

It accepts normalized identifiers, raw header strings, or Python standard-library
`email.message.Message` / `EmailMessage` objects. Missing roots, duplicate IDs,
malformed references, legacy encoded words, and hostile graph cycles are handled
without losing deterministic behavior or hanging.

## Capabilities

- Link full `References` chains without loops or stealing an established parent.
- When `References` is unusable, use only the first valid `In-Reply-To` ID as RFC
  5256 requires; ambiguous trailing addresses never become fabricated ancestry.
- Recover missing roots as dummy containers and prune them with the RFC root-level
  special case.
- Extract exact RFC 5256 base subjects, including list blobs, `Re:`/`Fw:`/`Fwd:`,
  `(fwd)` trailers, `[fwd: ...]` wrappers, folded whitespace, and RFC 2047 words.
- Compare subjects with RFC 5051 titlecase-plus-compatibility decomposition rather
  than Python `casefold()`.
- Optionally group disconnected roots by base subject while preserving RFC dummy
  ownership and reply/forward preference.
- Optionally sort roots and every sibling set by normalized sent date, including
  `INTERNALDATE` fallback, dummy first-child keys, and sequence-number tie-breaks.
- Project a thread tree onto a mailbox search result without mutating it.
- Serialize exact RFC 5256 `thread-data` or a complete untagged response using
  sequence numbers, UIDs, or a caller-supplied identifier resolver.
- Preserve the original parsed email object as payload by default.
- Remain iterative for deep chains and nested splits; runtime dependencies stay
  at zero.

## Install

```bash
pip install threadweave
```

The distribution includes a PEP 561 `py.typed` marker.

## Reference threading

```python
from threadweave import Message, thread_messages

threads = thread_messages([
    Message(message_id="a", subject="Deploy plan"),
    Message(
        message_id="b",
        references=["a"],
        in_reply_to="a",
        subject="Re: Deploy plan",
    ),
    Message(
        message_id="c",
        references=["a", "b"],
        subject="Re: Deploy plan",
    ),
])

assert len(threads) == 1
root = threads[0]
assert root.message.message_id == "a"
assert [node.message.message_id for node in root.iter_descendants()] == ["b", "c"]
```

Raw RFC header text works directly:

```python
thread_messages([
    Message(message_id="root@example.com"),
    Message(
        message_id="child@example.com",
        references="<root@example.com>",
        in_reply_to="<root@example.com> sender@example.net",
    ),
])
```

## Standard-library email adapter

```python
from email import policy
from email.parser import BytesParser

from threadweave import thread_email_messages

parsed = [
    BytesParser(policy=policy.default).parsebytes(raw_message)
    for raw_message in raw_messages
]
threads = thread_email_messages(parsed)

assert threads[0].message.payload is parsed[0]
```

`message_from_email` also accepts mailbox `internal_date`, `sequence_number`, and
`uid` metadata. Legacy `compat32` encoded words, unknown character-set labels,
and malformed values are decoded or preserved best-effort instead of aborting
mailbox ingestion.

## Subject extraction and comparison

```python
from threadweave import (
    is_reply_or_forward_subject,
    normalize_subject,
    unicode_casemap_key,
)

subject = "[project] Re: [fwd: Release plan (fwd)]"
assert normalize_subject(subject) == "Release plan"
assert is_reply_or_forward_subject(subject)

assert unicode_casemap_key("Ｔｏｐｉｃ") == unicode_casemap_key("Topic")
assert unicode_casemap_key("é") == unicode_casemap_key("e\u0301")
```

Subject grouping is a caller-selected fallback because unrelated conversations
can legitimately share a base subject:

```python
threads = thread_messages(messages, group_by_subject=True)
```

## RFC sent-date ordering

The historical default remains input order. Enable RFC 5256 ordering explicitly:

```python
threads = thread_messages(
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

assert [root.message.message_id for root in threads] == [
    "earlier@example.com",
    "later@example.com",
]
```

A valid `Date` is adjusted to UTC. Invalid zones are treated as UTC, invalid times
as local midnight, missing or unusable values fall back to `INTERNALDATE`, and a
message with neither usable value sorts at the earliest UTC instant. Exact ties
use unique positive mailbox sequence numbers.

## IMAP THREAD response serialization

```python
from threadweave import Message, serialize_thread_response, thread_messages

threads = thread_messages([
    Message(message_id="root", sequence_number=3),
    Message(message_id="child", references=["root"], sequence_number=6),
    Message(message_id="branch-a", references=["root", "child"], sequence_number=4),
    Message(message_id="branch-b", references=["root", "child"], sequence_number=44),
])

response = serialize_thread_response(threads)
assert response == "* THREAD (3 6 (4)(44))\r\n"
```

Use UID metadata for UID THREAD:

```python
response = serialize_thread_response(threads, identifier="uid")
```

A callable resolver supports mailbox identifiers stored outside `Message`:

```python
response = serialize_thread_response(
    threads,
    identifier=lambda message: message.payload.mailbox_uid,
)
```

Project only messages matching a server-side search result while retaining the
relationships contributed by excluded ancestors:

```python
response = serialize_thread_response(
    threads,
    include=lambda message: message.payload.matches_search,
)
```

An excluded or missing top-level parent with two matching children is emitted as
`((3)(5))`, as required by RFC 5256. Projection is non-mutating. The serializer
rejects cycles, shared container nodes, duplicate identifiers, invalid dummy
shapes, and values outside IMAP's non-zero unsigned 32-bit range. Response line
endings are restricted to CRLF or caller-owned framing to prevent line injection.

`serialize_thread_data` omits the untagged `"* "` prefix and CRLF when a protocol
framework owns response framing.

## Public API

| Symbol | Purpose |
|---|---|
| `Message` | Headers, payload, sent-date metadata, sequence number, and UID. |
| `thread_messages(..., group_by_subject=False, sort_by_sent_date=False)` | Build conversation trees from any iterable. |
| `Container` | Loop-safe mutable thread-tree node. |
| `message_from_email(...)` | Convert a stdlib email message and mailbox metadata. |
| `thread_email_messages(...)` | Thread stdlib messages directly. |
| `normalize_sent_date` | Normalize `Date` / `INTERNALDATE` to aware UTC. |
| `normalize_subject` | Exact RFC 5256 base-subject extraction. |
| `is_reply_or_forward_subject` | RFC reply/forward classification. |
| `unicode_casemap_key` | RFC 5051 comparison key. |
| `decode_header_text` | Tolerant RFC 2047 decoding. |
| `normalize_message_id` / `extract_reference_ids` | RFC 5322 ID parsing. |
| `generate_email_fingerprint` | Deterministic SHA-256 fallback identity. |
| `serialize_thread_data` | Render RFC `thread-data`. |
| `serialize_thread_response` | Render `* THREAD ...\r\n`. |
| `ThreadSerializationError` | Invalid graph or protocol metadata error. |

## Quality guarantees

- Python 3.10, 3.11, 3.12, and 3.13 CI matrix.
- **100%** production statement and branch coverage required.
- Docstrings required for every authored production module and callable.
- Ruff, `compileall`, doctests, dependency consistency, wheel/sdist build,
  `py.typed` inspection, and installed-wheel smoke tests.
- No runtime dependencies.
- Iterative graph processing for deep and malformed inputs.

## Standards and product boundary

Reference linking, dummy ownership, base-subject extraction, Unicode comparison,
sent-date sibling ordering, search projection, and THREAD response grammar follow
RFC 5256, RFC 5051, and the IMAP `nz-number` contract.

ThreadWeave does not implement mailbox authentication, command parsing, search
execution, UIDVALIDITY lifecycle, persistence, or socket framing. Those are
server responsibilities. Keeping them outside the package preserves one reusable
threading implementation for standalone Python, naruon, migration services,
archive viewers, and IMAP gateways.

Unicode collation follows the Unicode Character Database bundled with the active
Python runtime, as RFC 5051 permits. Visual confusables from unrelated scripts
remain distinct.

## Autonomous maintenance

Two staggered workflows keep development review-first and single-flight:

- minute 11 each hour: centrally governed PR review/fix/revalidation/merge;
- minute 41 each hour: one bounded product-development task only when no PR or
  active/unknown task exists.

The Agent Tasks API requires a supported user token in `COPILOT_GITHUB_TOKEN`
with Agent tasks read/write permission. Missing credentials or inventory errors
close the gate without creating duplicate work. Both workflows support dry runs.

## One source, multiple uses

The RFC 5322 header primitives were extracted behaviour-preserving from the
naruon control plane. The tree assembly, subject, collation, date, and IMAP
projection layers remain standalone APIs and can also be imported into naruon or
another service module.

## Research grounding

See [`docs/research`](docs/research/README.md) for JWZ, RFC 5256, RFC 5051, RFC
5322, RFC 2047, RFC 6532, IMAP response grammar and identifier limits,
Unicode-version caveats, and PEP 561.

## License

Apache-2.0. See [LICENSE](LICENSE).
