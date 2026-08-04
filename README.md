# threadweave

**Standards-grounded JWZ/RFC 5256 email reference threading for Python, with no
runtime dependencies.**

`threadweave` turns a flat iterable of messages into deterministic conversation
trees. It combines the JWZ container model with RFC 5322 identification fields,
RFC 2047 encoded-word decoding, RFC 5256 base-subject extraction and optional
sent-date ordering, and RFC 5051 `i;unicode-casemap` comparison.

It accepts normalized identifiers, raw header strings, or Python standard-library
`email.message.Message` objects. Malformed historical mail, missing roots,
duplicate identifiers, deep chains, and cyclic references terminate safely.

## Install

```bash
pip install threadweave
```

The wheel includes a PEP 561 `py.typed` marker. The runtime is pure Python
standard library and supports Python 3.10 through 3.13.

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
malformed values instead of aborting the mailbox ingest.

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

## Public API

| Symbol | Purpose |
|---|---|
| `Message` | Thread input plus payload and optional mailbox ordering metadata. |
| `Container` | Identity-based, loop-safe thread-tree node. |
| `thread_messages(...)` | Build JWZ/RFC 5256 thread roots from any iterable. |
| `message_from_email(...)` | Convert one stdlib email object. |
| `thread_email_messages(...)` | Convert and thread stdlib email objects. |
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
  on Python 3.10, 3.11, 3.12, and 3.13.
- CI builds wheel and source distributions, verifies `py.typed`, installs the
  wheel outside the source tree, and executes a smoke test.
- Graph operations are iterative and identity-guarded; deep or cyclic malformed
  input cannot recurse indefinitely.

## Autonomous maintenance

Two staggered workflows keep development review-first and single-flight.

At minute 11 of every hour, `hourly-pr-maintenance.yml` calls the organization
workflows in `ContextualWisdomLab/.github` to inspect reviews, dispatch bounded
fixes, revalidate the exact head, update branches, and merge only when policy is
satisfied.

At minute 41, `hourly-product-development.yml` runs only when the PR queue is
empty. Its trust boundary is deliberately split across fresh GitHub-hosted jobs:

1. A disposable, `.git`-free workspace runs OpenCode through NVIDIA NIM as UID
   65532 with an empty environment except for the scoped NIM credential.
2. `scripts/ci/hourly_product_guard.py` accepts only bounded text changes under
   `src/threadweave/`, `tests/`, `docs/`, `README.md`, and `CHANGELOG.md`.
   Workflow, policy, dependency, release, deletion, link, binary, mode, size, and
   secret-leak changes fail closed.
3. Only the sealed patch, digest, path inventory, and sanitized PR metadata cross
   the job boundary. A fresh credential-free job reapplies and independently
   verifies that exact patch.
4. A separate publisher job starts from a fresh `main`, rechecks that no PR or
   base movement occurred, reapplies the same digest, and opens one PR. The model
   runner never shares a process, filesystem, Git hook, or GitHub credential with
   publication.

Configure these organization or repository secrets:

- `NVIDIA_NIM_API_KEY`: scoped and rotatable model credential.
- `PR_REVIEW_MERGE_TOKEN` or `OPENCODE_APPROVE_TOKEN`: fine-grained PAT or GitHub
  App token used only by the fresh publisher job.

The external automation token is intentional. GitHub documents that a pull
request created with the repository `GITHUB_TOKEN` leaves its workflow runs
awaiting approval; a GitHub App token or personal access token lets the required
PR workflows start without that manual gate. The product-development agent never
merges, tags, or publishes a release.

Both workflows expose a manual `dry_run` input. Missing credentials, an open PR,
a moved base, a changed patch digest, or an unavailable safe proposal stops the
cycle without mutation.

## Architecture and standards boundary

The package remains useful both as a standalone dependency and as a module in
`naruon` or another service. The threading, subject, collation, and date layers
are transport-neutral. IMAP `THREAD` response serialization remains a separate
presentation layer rather than leaking protocol state into the core model.

See [`docs/research`](docs/research/README.md) for JWZ, RFC 5322, RFC 2047,
RFC 5051, RFC 5256, RFC 6532, Unicode-version boundaries, and PEP 561.

## License

Apache-2.0. See [LICENSE](LICENSE).
