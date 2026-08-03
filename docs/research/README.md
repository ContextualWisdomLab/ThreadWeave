# Research grounding

`threadweave` implements established, documented standards and algorithms rather
than an ad-hoc heuristic. The primary sources are listed below.

## Message threading — JWZ and RFC 5256 REFERENCES

- **Jamie Zawinski, “message threading”**
  (<https://www.jwz.org/doc/threading.html>) provides the influential container-
  based algorithm used by mature mail clients.
- **RFC 5256, “Internet Message Access Protocol — SORT and THREAD Extensions”**
  (<https://www.rfc-editor.org/rfc/rfc5256>) standardizes the `REFERENCES`
  threading algorithm. Its steps implemented here are:
  1. Build an `id_table` mapping normalized `Message-ID` values to containers;
     link `References` entries into a parent chain without loops and without
     overriding a container that already has a parent.
  2. When a usable `References` chain is absent, use the **first valid**
     `In-Reply-To` identifier as the message's only reference. RFC 5256 applies
     this restriction because real-world `In-Reply-To` fields frequently contain
     addresses or other ambiguous material after the first identifier.
  3. Gather the **root set**: every container with no parent.
  4. **Prune empty containers**: remove empty childless containers; splice the
     children of an empty container up into its level; at the root level, retain
     an empty container with multiple children as the missing-thread-root
     grouping node, but promote its only child when it has exactly one.
  5. Optionally gather root threads by base subject. The RFC 5256 subject table
     retains a dummy container as owner whenever one exists; otherwise it prefers
     a non-reply/non-forward message over a reply/forward message.
  6. Return the resulting thread roots. Date sorting from the IMAP `THREAD`
     response algorithm is intentionally outside the current transport-agnostic
     API because `Message` does not yet require a sent-date field.

## Identification fields — RFC 5322 §3.6.4

- **RFC 5322, “Internet Message Format”, §3.6.4 (Identification Fields)**
  (<https://www.rfc-editor.org/rfc/rfc5322#section-3.6.4>) defines the
  `Message-ID`, `In-Reply-To`, and `References` header fields and the
  `msg-id = "<" id-left "@" id-right ">"` grammar.
- Both `In-Reply-To` and `References` can contain one or more message
  identifiers. Consequently, `threadweave.Message` accepts either a raw header
  string or an already-split sequence for each field. The parser exposes every
  identifier in first-seen order and removes duplicates; the threading layer then
  applies RFC 5256's first-valid-only rule specifically to the `In-Reply-To`
  fallback.
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

Subject grouping is a **heuristic**, not part of the reference-based threading
guarantee. Distinct conversations can share a subject, and localized
reply/forward syntax varies, so it is off by default
(`group_by_subject=False`). The current lightweight base-subject parser handles
common `Re:`, `Fwd:`, and `Fw:` prefixes; a future strict RFC 5256 mode can add
the full internationalized base-subject extraction grammar and sent-date
ordering without changing the reference-linking core.

## Provenance

The RFC 5322 header primitives (`normalize_message_id`,
`extract_reference_ids`, `generate_email_fingerprint`) are extracted
behaviour-preserving from the naruon control plane
(`backend/services/threading_service.py`). The threading assembly is a fresh
implementation built on the JWZ container model and RFC 5256 semantics, so
improvements can be ported in both directions.
