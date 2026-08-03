# threadweave

**Standards-grounded JWZ/RFC 5256 email reference threading for Python — pure
stdlib, zero runtime dependencies.**

`threadweave` turns a flat iterable of email messages into conversation trees
using Jamie Zawinski's container algorithm and the reference-linking semantics
standardized by RFC 5256. It builds on RFC 5322 identification fields, RFC 2047
encoded-word decoding, exact RFC 5256 base-subject extraction, and RFC 5051
`i;unicode-casemap` subject comparison.

It accepts normalized identifiers or raw header strings and integrates directly
with Python's standard-library `email.message.Message` / `EmailMessage` objects.
The implementation is deterministic and loop-safe even when historical or
hostile mail contains missing roots, duplicate identifiers, malformed references,
or cyclic graph edges.

## What it does

- Builds the JWZ id-table of containers and links `References` chains **without
  creating loops** and **without overriding a message's good existing parent**.
- Accepts raw RFC identification headers, including multiple identifiers, as
  well as already-split sequences.
- Uses a valid `References` chain in full; when it is unavailable, follows RFC
  5256 by using only the **first valid** `In-Reply-To` identifier as the parent.
- Recovers missing roots as empty placeholder containers, then prunes empty
  containers with the RFC 5256 root-level special case.
- Implements RFC 5256 base-subject extraction: RFC 2047 decoding, whitespace
  normalization, `Re:`/`Fw:`/`Fwd:` leaders, mailing-list blobs, `(fwd)`
  trailers, and `[fwd: ...]` wrappers.
- Compares base subjects with RFC 5051 `i;unicode-casemap`: per-codepoint Unicode
  titlecasing followed by recursive canonical and compatibility decomposition.
  Case, canonical-composition, and compatibility-width variants therefore group
  consistently without collapsing unrelated scripts.
- Optionally groups root threads by base subject while preserving RFC 5256 dummy-
  container and reply-or-forward ownership semantics. This heuristic is off by
  default because unrelated conversations can share a subject.
- Threads parsed standard-library email objects without manual header mapping;
  each source object is retained as the default payload.
- Decodes RFC 2047 encoded words under modern and legacy parser policies,
  recovers unknown character sets best-effort, and preserves malformed values
  rather than aborting mailbox ingestion.

## Install

```bash
pip install threadweave
```

The runtime uses only the Python standard library. The distribution includes a
PEP 561 `py.typed` marker so type checkers consume the inline annotations.

## Quickstart

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
    Message(message_id="c", references=["a", "b"], subject="Re: Deploy plan"),
])

assert len(threads) == 1
root = threads[0]
assert root.message.message_id == "a"
assert [node.message.message_id for node in root.iter_descendants()] == ["b", "c"]
```

Raw RFC header strings work directly:

```python
thread_messages([
    Message(message_id="a@example.com"),
    Message(
        message_id="b@example.com",
        references="<a@example.com>",
        in_reply_to="<a@example.com>",
    ),
])
```

When `References` is unavailable, only the first valid `In-Reply-To` identifier
is used. Ambiguous trailing values never become a fabricated ancestry chain:

```python
thread_messages([
    Message(message_id="root@example.com"),
    Message(
        message_id="child@example.com",
        in_reply_to="<root@example.com> sender@example.net",
    ),
])
```

For parsed email messages, use the standard-library adapter:

```python
from email import policy
from email.parser import BytesParser

from threadweave import thread_email_messages

parsed_messages = [
    BytesParser(policy=policy.default).parsebytes(raw_message)
    for raw_message in raw_messages
]
threads = thread_email_messages(parsed_messages)

assert threads[0].message.payload is parsed_messages[0]
```

Extract and compare standardized subjects directly:

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

Enable subject fallback only when reference headers are insufficient:

```python
threads = thread_messages(messages, group_by_subject=True)
```

## API

| Symbol | Purpose |
|---|---|
| `Message` | Input dataclass: `message_id`, raw-or-split `in_reply_to` / `references`, `subject`, and `payload`. |
| `thread_messages(messages, *, group_by_subject=False)` | Run the JWZ/RFC 5256 reference-threading core over any iterable. |
| `message_from_email(message, *, payload=...)` | Convert a stdlib email message and retain the source object by default. |
| `thread_email_messages(messages, *, group_by_subject=False)` | Thread stdlib email messages directly. |
| `Container` | Loop-safe thread-tree node with parent, children, and deterministic traversal. |
| `decode_header_text` | Tolerant RFC 2047 encoded-word decoder. |
| `normalize_message_id` / `extract_reference_ids` | RFC 5322 identification-field parsing. |
| `generate_email_fingerprint` | Deterministic SHA-256 identity fallback. |
| `normalize_subject` | Exact RFC 5256 base-subject extraction. |
| `is_reply_or_forward_subject` | RFC 5256 reply-or-forward classification. |
| `is_reply_subject` | Compatibility alias for the standardized classification. |
| `unicode_casemap_key` | RFC 5051 `i;unicode-casemap` preparation key. |

## Quality guarantees

- CI runs on Python 3.10, 3.11, 3.12, and 3.13.
- Production statement and branch coverage are both required to remain at
  **100%**.
- Every authored production module, class, method, property, and function must
  have a docstring.
- CI compiles source and tests, runs doctests, validates dependency consistency,
  builds wheel and source distributions, verifies `py.typed`, and smoke-tests the
  installed wheel outside the source tree.
- Runtime dependencies remain zero.

## Unicode and security boundary

`unicode_casemap_key` uses the Unicode Character Database bundled with the
running Python version. RFC 5051 permits implementations based on different
Unicode revisions to vary when newly assigned characters gain titlecase or
decomposition properties. The collation is locale-independent and deliberately
does not treat visual confusables as equal: Latin `A`, Greek `Α`, and Cyrillic
`А` remain different keys.

The public collation primitive expects already-decoded Unicode text. Raw and
legacy encoded headers should enter through `decode_header_text` or the stdlib
email adapter first.

## Standards boundary

Reference linking, dummy-container ownership, base-subject extraction, and
subject comparison follow RFC 5256 and RFC 5051. Optional subject grouping
remains a heuristic because distinct conversations can legitimately share one
base subject. The transport-agnostic `Message` model does not yet require sent
dates, so RFC 5256 sent-date sorting and IMAP `THREAD` response serialization
remain outside the current core.

## Autonomous maintenance

Two staggered scheduled workflows keep development single-flight and review-
first:

- At minute 11 each hour, `hourly-pr-maintenance.yml` invokes the organization-
  governed review-fix and merge schedulers from `ContextualWisdomLab/.github`.
- At minute 41 each hour, `hourly-product-development.yml` creates one bounded
  Copilot cloud-agent task only when there is no open pull request and no active
  or unknown-state task. Inventory failure closes the gate.

The Agent Tasks REST API requires a supported user token. Configure
`COPILOT_GITHUB_TOKEN` as a fine-grained personal access token with Agent tasks
read/write permission for this repository and an eligible Copilot Business or
Enterprise user. Without it, the workflow records the prerequisite and exits
without mutation. Both workflows provide a manual `dry_run` input.

## One source, multi use

The RFC 5322 header primitives in `src/threadweave/headers.py` were extracted
behaviour-preserving from the naruon control plane. The assembly and collation
layers are standalone APIs but remain suitable for import into naruon or another
service module.

## Research grounding

See [`docs/research`](docs/research/README.md) for JWZ, RFC 5256, RFC 5051, RFC
5322, RFC 2047, RFC 6532, Unicode-version caveats, and PEP 561.

## License

Apache-2.0. See [LICENSE](LICENSE).
