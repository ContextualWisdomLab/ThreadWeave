# threadweave

**Standards-grounded JWZ/RFC 5256 email reference threading for Python — pure
stdlib, zero runtime dependencies.**

`threadweave` turns a flat iterable of email messages into conversation trees
using Jamie Zawinski's container algorithm and the reference-linking semantics
standardized by RFC 5256, built on RFC 5322 §3.6.4 identification-field parsing
(`Message-ID`, `References`, `In-Reply-To`). It accepts normalized identifiers or
raw header strings and integrates directly with Python's standard-library
`email.message.Message` / `EmailMessage` objects.

It exists because the obviously-wrong approaches — grouping by subject alone, or
naively chaining every value found in `In-Reply-To` — mis-thread real mail:
subjects collide across unrelated conversations, references arrive out of order,
roots go missing, malformed headers contain ambiguous trailing material, and
hostile inputs form reference loops. `threadweave` handles these cases
deterministically and **loop-safely**.

## What it does

- Builds the JWZ id-table of containers and links `References` chains **without
  creating loops** and **without overriding a message's good existing parent**.
- Accepts raw RFC identification headers, including multiple identifiers, as
  well as already-split sequences.
- Uses a valid `References` chain in full; when it is unavailable, follows RFC
  5256 by using only the **first valid** `In-Reply-To` identifier as the parent.
- Recovers missing roots as empty placeholder containers, then **prunes** empty
  containers correctly (removing childless empties and splice-promoting the
  children of empty ones, with the root-level single-child special case).
- Implements RFC 5256 base-subject extraction: RFC 2047 decoding, whitespace
  normalization, `Re:`/`Fw:`/`Fwd:` leaders, mailing-list blobs, `(fwd)`
  trailers, and `[fwd: ...]` wrappers.
- Optionally groups the root set by base subject while preserving RFC 5256
  dummy-container and reply-or-forward ownership semantics. This heuristic is
  off by default because unrelated conversations can share a subject.
- Threads parsed standard-library email objects without manual header mapping;
  each source object is retained as the default payload.
- Decodes RFC 2047 encoded words even under the legacy `compat32` parser policy,
  recovers unknown character sets best-effort, and preserves malformed values
  rather than aborting mailbox ingestion.
- Terminates on adversarial input: self-references and mutual reference cycles
  never loop or crash.

## Install

```bash
pip install threadweave
```

No runtime dependencies — only the standard library (`email`, `re`, `hashlib`,
`dataclasses`, `typing`). The distribution includes a PEP 561 `py.typed` marker,
so type checkers consume its inline annotations directly.

## Quickstart

```python
from threadweave import Message, thread_messages

threads = thread_messages([
    Message(message_id="a", subject="Deploy plan"),
    Message(message_id="b", in_reply_to="a", references=["a"], subject="Re: Deploy plan"),
    Message(message_id="c", references=["a", "b"], subject="Re: Deploy plan"),
])

assert len(threads) == 1            # one conversation
root = threads[0]                   # a Container
print(root.message.message_id)      # "a"
for node in root.iter_descendants():
    print(node.message.message_id)  # "b", then "c"
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

When `References` is absent, only the first valid `In-Reply-To` identifier is
used. This avoids turning ambiguous trailing values into a fabricated chain:

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

# The original parsed object is carried through unchanged.
assert threads[0].message.payload is parsed_messages[0]
```

Extract exact RFC 5256 base subjects directly:

```python
from threadweave import is_reply_or_forward_subject, normalize_subject

subject = "[project] Re: [fwd: Release plan (fwd)]"
assert normalize_subject(subject) == "Release plan"
assert is_reply_or_forward_subject(subject)
```

Group unrelated-but-same-subject roots when references are missing:

```python
threads = thread_messages(messages, group_by_subject=True)
```

## API

| Symbol | Purpose |
|---|---|
| `Message` | Input dataclass: `message_id`, raw-or-split `in_reply_to` / `references`, `subject`, `payload`. |
| `thread_messages(messages, *, group_by_subject=False)` | Run the JWZ/RFC 5256 reference-threading core over any iterable; return root `Container` objects. |
| `message_from_email(message, *, payload=...)` | Convert a stdlib email message while retaining the source object by default. |
| `thread_email_messages(messages, *, group_by_subject=False)` | Thread an iterable of stdlib email messages directly. |
| `Container` | Thread-tree node: `message`, `parent`, `children`, `is_empty`, `add_child`, `iter_descendants`. |
| `decode_header_text` | Decode RFC 2047 encoded words with tolerant charset and malformed-input handling. |
| `normalize_message_id` / `extract_reference_ids` | RFC 5322 `Message-ID` / reference-header parsing. |
| `generate_email_fingerprint` | Deterministic SHA-256 identity for messages lacking a usable `Message-ID`. |
| `normalize_subject` | Exact RFC 5256 base-subject extraction. |
| `is_reply_or_forward_subject` | RFC 5256 reply-or-forward classification. |
| `is_reply_subject` | Compatibility name for `is_reply_or_forward_subject`. |

`Container.iter_descendants` and the internal linking are loop-safe: traversal
visits each node at most once, so a cyclic reference graph can never hang.

## Quality guarantees

- CI runs on Python 3.10, 3.11, 3.12, and 3.13.
- Production statement and branch coverage are both required to remain at
  **100%**.
- Every production module, class, method, property, and function is required to
  carry a docstring.
- CI compiles the source, runs doctests, checks dependency consistency, builds
  both wheel and source distributions, verifies the `py.typed` marker, and
  smoke-tests the installed wheel outside the source tree.

## Autonomous maintenance

Two staggered scheduled workflows keep development single-flight and review-
first:

- At minute 11 each hour, `hourly-pr-maintenance.yml` invokes the organization-
  governed review-fix and merge schedulers from `ContextualWisdomLab/.github`.
  Review feedback, branch updates, checks, and merge policy remain centralized.
- At minute 41 each hour, `hourly-product-development.yml` creates one bounded
  Copilot cloud-agent task only when there is no open pull request and no active
  or unknown-state agent task. Inventory failure is treated as a closed gate, so
  an API outage cannot create duplicate work.

The Agent Tasks REST API does not accept the installation token behind
`GITHUB_TOKEN`. Configure the repository or organization secret
`COPILOT_GITHUB_TOKEN` with a fine-grained personal access token that has **Agent
tasks: read and write** permission for this repository. The authenticated user
must also have an eligible Copilot Business or Enterprise subscription. Without
that secret, the workflow records the missing prerequisite and exits without
mutation. Both workflows expose a manual `dry_run` input for safe verification.

Contract tests pin the supported API version, dedicated-token boundary, active-
task terminal states, centralized maintenance calls, bounded test-first prompt,
and prohibition on product-task self-merging.

## Standards boundary

Reference linking, dummy-container ownership, and base-subject extraction follow
RFC 5256. Optional subject grouping remains a heuristic because distinct
conversations can legitimately share one base subject. The transport-agnostic
`Message` API does not yet require sent dates, so RFC 5256's date-sorting steps
and IMAP response serialization remain outside the current core.

## One source, multi use (OSMU)

The RFC 5322 header primitives in
[`threadweave/headers.py`](src/threadweave/headers.py) are extracted
**behaviour-preserving** from a production control plane
([naruon](https://github.com/ContextualWisdomLab/naruon)), where they normalize
`Message-ID`/reference headers for canonical email threading. The assembly here
is a fresh implementation built on those primitives — one source, usable both as
a standalone dependency and as a git submodule.

## Research grounding

See [`docs/research`](docs/research/README.md): Zawinski's container algorithm,
RFC 5256 `REFERENCES` threading and base-subject extraction, RFC 5322 §3.6.4
identification fields, RFC 2047 encoded words, RFC 6532 internationalized email
headers, and PEP 561 typed-package distribution.

## License

Apache-2.0. See [LICENSE](LICENSE).
