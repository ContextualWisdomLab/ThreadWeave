# Research grounding

`threadweave` implements established, documented standards and algorithms rather
than an ad-hoc heuristic. The primary sources are listed below.

## Message threading — the JWZ algorithm

- **Jamie Zawinski, “message threading”**
  (<https://www.jwz.org/doc/threading.html>). The canonical description of the
  algorithm used by Netscape Mail, Mozilla/Thunderbird, and other mature mail
  clients. The steps implemented here are:
  1. Build an `id_table` mapping `Message-ID` to a `Container`; for each message
     find or create its container, then link every `References` entry into a
     parent chain — **without** creating loops and **without** overriding a
     container that already has a parent — and set the message's parent to the
     last reference.
  2. Gather the **root set**: every container with no parent.
  3. Discard the `id_table`.
  4. **Prune empty containers**: nuke empty childless containers; splice the
     children of an empty container up into its level; at the root level, keep
     an empty container that has more than one child (it groups a thread whose
     root was never seen), but promote its single child when it has exactly one.
  5. Optionally **group the root set by base subject** (`Re:`/`Fwd:`/`Fw:`
     prefixes stripped).
  6. The result is a set of threads.

## Identification fields — RFC 5322 §3.6.4

- **RFC 5322, “Internet Message Format”, §3.6.4 (Identification Fields)**
  (<https://www.rfc-editor.org/rfc/rfc5322#section-3.6.4>) defines the
  `Message-ID`, `In-Reply-To`, and `References` header fields and the
  `msg-id = "<" id-left "@" id-right ">"` grammar.
- Both `In-Reply-To` and `References` are defined as one or more message
  identifiers. Consequently, `threadweave.Message` accepts either a raw header
  string or an already-split sequence for each field. The parser extracts every
  identifier, preserves first appearance, and drops duplicates.
- `threadweave.headers` strips angle brackets and also supports a whitespace
  fallback for malformed but recoverable values. This is deliberately tolerant
  ingestion; the normalized identifiers remain the algorithm's internal form.

## Encoded words — RFC 2047

- **RFC 2047, “Message Header Extensions for Non-ASCII Text”**
  (<https://www.rfc-editor.org/rfc/rfc2047>) defines MIME encoded words such as
  `=?utf-8?b?...?=` for non-ASCII header text.
- Modern `EmailMessage` policies decode these values transparently, while the
  legacy `compat32` policy can expose the transport representation. The adapter
  therefore decodes RFC 2047 parts explicitly, preserves ordinary text between
  encoded words, recovers unknown character-set labels with replacement
  decoding, and retains a malformed encoded word verbatim rather than rejecting
  the whole message.

## Internationalized headers — RFC 6532

- **RFC 6532, “Internationalized Email Headers”**
  (<https://www.rfc-editor.org/rfc/rfc6532>) extends the Internet Message Format
  to permit UTF-8 in most header values. The standard-library adapter retains
  decoded header text as Unicode, including non-ASCII subjects, rather than
  performing lossy ASCII coercion.

## Typed-package distribution — PEP 561

- **PEP 561, “Distributing and Packaging Type Information”**
  (<https://peps.python.org/pep-0561/>) specifies the `py.typed` marker for
  packages that distribute inline type information. `threadweave` ships this
  marker and CI verifies that it is present in both wheel and source archives.

## A note on base-subject grouping

Subject grouping (step 5) is a **heuristic**, not part of the reference-based
threading guarantee. Distinct conversations can share a subject, and localized
reply/forward prefixes vary, so it is off by default (`group_by_subject=False`)
and applied only as a fallback for messages whose `References`/`In-Reply-To`
chains do not already connect them.

## Provenance

The RFC 5322 header primitives (`normalize_message_id`,
`extract_reference_ids`, `generate_email_fingerprint`) are extracted
behaviour-preserving from the naruon control plane
(`backend/services/threading_service.py`). The JWZ assembly is a fresh canonical
implementation built on top of them, so improvements can be ported in both
directions.
