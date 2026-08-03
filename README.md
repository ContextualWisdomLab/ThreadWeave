# threadweave

**The canonical JWZ email message-threading algorithm for Python — pure
stdlib, zero runtime dependencies.**

`threadweave` turns a flat list of email messages into conversation trees using
[Jamie Zawinski's threading algorithm](https://www.jwz.org/doc/threading.html),
built on top of RFC 5322 §3.6.4 identification-field parsing (`Message-ID`,
`References`, `In-Reply-To`). It accepts either normalized identifiers or raw
header strings and integrates directly with Python's standard-library
`email.message.Message` / `EmailMessage` objects.

It exists because the obviously-wrong approaches — grouping by subject alone, or
naively chaining `In-Reply-To` — mis-thread real mail: subjects collide across
unrelated conversations, references arrive out of order, roots go missing, and
malformed headers form reference loops. JWZ handles all of these; `threadweave`
implements it faithfully and **loop-safely**.

## What it does

- Builds the JWZ id-table of containers and links `References` chains **without
  creating loops** and **without overriding a message's good existing parent**.
- Accepts raw RFC identification headers, including multiple message identifiers
  in either `References` or `In-Reply-To`, as well as already-split sequences.
- Recovers missing roots as empty placeholder containers, then **prunes** empty
  containers correctly (nuking childless empties and splice-promoting the
  children of empty ones, with the special root-level single-child handling).
- Optionally groups the root set by **base subject** (`Re:`/`Fwd:`/`Fw:`
  stripped) — a heuristic, off by default.
- Threads parsed standard-library email objects without manual header mapping;
  each source object is retained as the default payload.
- Terminates on adversarial input: self-references and mutual reference cycles
  never loop or crash.

## Install

```bash
pip install threadweave
```

No runtime dependencies — only the standard library (`email`, `re`, `hashlib`,
`dataclasses`, `typing`).

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

Group unrelated-but-same-subject roots when references are missing:

```python
threads = thread_messages(messages, group_by_subject=True)
```

## API

| Symbol | Purpose |
|---|---|
| `Message` | Input dataclass: `message_id`, raw-or-split `in_reply_to` / `references`, `subject`, `payload`. |
| `thread_messages(messages, *, group_by_subject=False)` | Run the JWZ algorithm over any iterable; returns the root `Container` list. |
| `message_from_email(message, *, payload=...)` | Convert a stdlib email message while retaining the source object by default. |
| `thread_email_messages(messages, *, group_by_subject=False)` | Thread an iterable of stdlib email messages directly. |
| `Container` | Thread-tree node: `message`, `parent`, `children`, `is_empty`, `add_child`, `iter_descendants`. |
| `normalize_message_id` / `extract_reference_ids` | RFC 5322 `Message-ID` / `References` parsing. |
| `generate_email_fingerprint` | Deterministic SHA-256 identity for messages lacking a usable `Message-ID`. |
| `normalize_subject` / `is_reply_subject` | Base-subject stripping and reply detection. |

`Container.iter_descendants` and the internal linking are loop-safe: traversal
visits each node at most once, so a cyclic reference graph can never hang.

## One source, multi use (OSMU)

The RFC 5322 header primitives in
[`threadweave/headers.py`](src/threadweave/headers.py) are extracted
**behaviour-preserving** from a production control plane
([naruon](https://github.com/ContextualWisdomLab/naruon)), where they normalize
`Message-ID`/`References` headers for canonical email threading. The JWZ
assembly here is a **fresh canonical implementation** built on top of those
primitives — one source, usable both as a standalone dependency and as a git
submodule.

## Research grounding

See [`docs/research`](docs/research/README.md): Zawinski's threading algorithm,
RFC 5322 §3.6.4 identification fields, and RFC 6532 internationalized email
headers. Base-subject grouping is documented there as a heuristic fallback.

## License

Apache-2.0. See [LICENSE](LICENSE).
