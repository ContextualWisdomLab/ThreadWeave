# Research grounding

`threadweave` implements an established, documented algorithm rather than an
ad-hoc heuristic. The primary sources:

## Message threading — the JWZ algorithm

- **Jamie Zawinski, "message threading"**
  (<https://www.jwz.org/doc/threading.html>). The canonical description of the
  algorithm used by Netscape Mail, Mozilla/Thunderbird, and most serious mail
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

- **RFC 5322, "Internet Message Format", §3.6.4 (Identification Fields)** defines
  the `Message-ID`, `In-Reply-To`, and `References` header fields and the
  `msg-id = "<" id-left "@" id-right ">"` grammar. `threadweave.headers` parses
  these: it strips the angle brackets, de-duplicates references while preserving
  header order, and falls back to whitespace splitting for malformed values.

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
