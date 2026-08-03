# Research grounding

`threadweave` implements published standards and algorithms rather than an ad-hoc
mailbox heuristic. The primary sources and implemented boundaries are below.

## Message threading — JWZ and RFC 5256 REFERENCES

- **Jamie Zawinski, “message threading”**
  (<https://www.jwz.org/doc/threading.html>) provides the influential container-
  based algorithm used by mature mail clients.
- **RFC 5256, “Internet Message Access Protocol — SORT and THREAD Extensions”**
  (<https://www.rfc-editor.org/rfc/rfc5256>) standardizes the `REFERENCES`
  threading algorithm and `THREAD` response format.

The implemented tree-construction steps are:

1. Build an `id_table` mapping normalized `Message-ID` values to containers.
   Link `References` entries into a parent chain without loops and without
   overriding a container that already has a good parent.
2. When a usable `References` chain is absent, use the **first valid**
   `In-Reply-To` identifier as the message's only reference. Historical fields
   often contain addresses or ambiguous material after that first identifier.
3. Gather every parentless container into the root set.
4. Prune dummy containers: remove empty leaves, splice-promote empty internal
   containers, and retain a multi-child dummy at the root as a missing-thread-
   root grouping node.
5. Optionally gather root threads by standardized base subject. A dummy owner is
   retained whenever one exists; otherwise a non-reply/non-forward owner is
   preferred.
6. Optionally apply both sent-date sorting stages described below.
7. Return transport-neutral `Container` trees.

## Base-subject extraction — RFC 5256 §2.1 and §5

`normalize_subject` implements the fixed seven-step procedure required by RFC
5256:

1. Decode RFC 2047 words; convert tabs and folded lines to spaces; collapse
   repeated ASCII spaces.
2. Repeatedly remove trailing whitespace and `(fwd)` trailers.
3. Remove a leading `subj-leader`: optional list blobs followed by a case-
   insensitive `Re:`, `Fw:`, or `Fwd:` token, including the optional blob between
   token and colon.
4. Remove a leading `subj-blob` only when a non-empty base remains. A final blob
   may therefore be the complete subject.
5. Repeat leader and blob removal until stable.
6. Unwrap a surrounding `[fwd: ...]` form and restart from trailer removal.
7. Return the resulting text.

RFC 5256 classifies a message as a reply or forward when extraction removes a
`subj-refwd`, `(fwd)` trailer, or `[fwd: ...]` wrapper.
`is_reply_or_forward_subject` exposes that result. Removing a list blob alone
does not classify the message.

## Subject comparison — RFC 5051 i;unicode-casemap

**RFC 5051, “i;unicode-casemap — Simple Unicode Collation Algorithm”**
(<https://www.rfc-editor.org/rfc/rfc5051>) defines the preparation RFC 5256 uses
for subject comparison:

1. Read one Unicode code point.
2. Apply its simple titlecase mapping from `UnicodeData.txt`; use simple uppercase
   if no titlecase mapping exists, otherwise leave it unchanged.
3. Recursively apply canonical or compatibility decomposition.
4. Append the result and continue.
5. Compare the prepared values with octet equality/order semantics.

Python's `str.title()` exposes full titlecase mappings and can expand one code
point through `SpecialCasing.txt`; that is not the RFC operation. The internal
`_simple_titlecase` helper keeps only one-code-point mappings and retains the
original code point when Python returns an expansion. `unicode_casemap_key` then
applies NFKD. Tests cover ASCII case, full-width forms, canonical equivalents,
RFC 5051's DZ-with-caron example, `ß`/`ﬀ` full-mapping boundaries, and unrelated-
script confusables.

RFC 5051 permits results to vary with the Unicode revision. ThreadWeave uses the
Unicode Character Database bundled with the active supported Python runtime and
documents that boundary rather than hard-coding an obsolete table.

## Sent-date ordering — RFC 5256 §2.2 steps 4 and 6

`normalize_sent_date` and `sort_by_sent_date=True` implement the RFC rules:

1. Parse the RFC 5322 `Date` and adjust a valid value to UTC.
2. Treat an invalid or absent zone as UTC.
3. Treat an invalid time as `00:00:00` in the recovered local zone.
4. If `Date` is missing or cannot provide a valid calendar date, use mailbox
   `INTERNALDATE`.
5. If neither value is usable, use the earliest representable UTC instant.
6. Break exact sent-date ties with the positive mailbox sequence number.
7. Before subject grouping, sort top-level roots. For a dummy root, sort its
   children first and use the first child's key as the dummy key.
8. After subject grouping, sort every sibling set bottom-up.

Naive `datetime` values follow the invalid-zone rule and are interpreted as UTC.
RFC 5322 permits leap-second value `60`; because Python cannot represent that
second directly, ThreadWeave uses the final microsecond before the following
minute, preserving order after second `59` and before the next minute.

Ordering is opt-in for source compatibility. Omitted sequence numbers use one-
based input position. Every effective value must be a unique positive integer;
explicit/implicit collisions are rejected.

## IMAP THREAD response projection — RFC 5256 §3 and §5

RFC 5256 defines a `THREAD` response as zero or more parenthesized thread lists.
Within a list, successive numbers are parent and child. When a parent has more
than one child, each sibling branch becomes a nested list. The RFC example is:

```text
* THREAD (2)(3 6 (4 23)(44 7 96))
```

A dummy parent has no identifier. Two matching children under a missing or
excluded parent are therefore represented as:

```text
* THREAD ((3)(5))
```

The relevant ABNF is equivalent to:

```text
thread-data    = "THREAD" [SP 1*thread-list]
thread-list    = "(" thread-members ")"
thread-members = nz-number *(SP nz-number) *thread-nested
thread-nested  = 2*thread-list
```

`serialize_thread_data` renders the data item. `serialize_thread_response` adds
the untagged `"* "` prefix and CRLF. Parent-child chains use spaces; separate top-
level threads and sibling lists are concatenated exactly as the grammar permits.

### Search-result projection

An IMAP server threads a search result while retaining relationships contributed
by messages outside that result. ThreadWeave accepts an `include(Message)`
predicate and performs a non-mutating projection:

- an excluded leaf disappears;
- an excluded internal message is splice-promoted so matching descendants remain
  below the nearest included ancestor;
- one promoted branch becomes a normal root;
- two or more promoted top-level branches retain an identifier-less dummy root.

Projection copies only protocol response nodes. It never changes source
`Container.parent`, `children`, message objects, or ordering.

### Sequence numbers, UIDs, and nz-number

RFC 5256 uses message sequence numbers for `THREAD` and UIDs for UID `THREAD`.
The serializer selects `Message.sequence_number`, `Message.uid`, or a caller-
supplied resolver for external mailbox metadata.

The IMAP base grammar in RFC 3501 and its successor RFC 9051 defines
`nz-number` as a non-zero unsigned 32-bit integer. ThreadWeave accepts values
from 1 through 4,294,967,295 and rejects zero, booleans, non-integers, larger
values, missing UID metadata, and duplicate emitted identifiers.

### Graph and response safety

Serialization is iterative, so deep linear chains and deeply nested sibling
splits do not hit Python's recursion limit. The protocol boundary rejects rather
than truncates or guesses:

- graph cycles;
- a container reachable from multiple positions;
- non-`Container` roots or children;
- concrete containers not wrapping `threadweave.Message`;
- identifier-less nodes outside the top-level dummy position;
- dummy roots with fewer than two branches;
- duplicate or out-of-range identifiers;
- arbitrary response line endings that could enable response splitting.

Only CRLF or an empty caller-owned suffix is accepted.

## Identification fields — RFC 5322 §3.6.4

**RFC 5322, “Internet Message Format”, §3.6.4**
(<https://www.rfc-editor.org/rfc/rfc5322#section-3.6.4>) defines `Message-ID`,
`In-Reply-To`, `References`, and `msg-id`. The public model accepts raw text or
already-split sequences. Parsing preserves first appearance and removes
duplicates; the threading layer then applies RFC 5256's first-valid-only rule to
the `In-Reply-To` fallback. Angle brackets are stripped and recoverable
whitespace-delimited historical values are tolerated.

## Encoded words and internationalized headers

- **RFC 2047** (<https://www.rfc-editor.org/rfc/rfc2047>) defines MIME encoded
  words. `decode_header_text` decodes them, preserves ordinary interstitial text,
  recovers unknown charset labels with replacement decoding, and retains damaged
  syntax verbatim rather than rejecting the message.
- **RFC 6532** (<https://www.rfc-editor.org/rfc/rfc6532>) permits UTF-8 in most
  header values. The stdlib adapter carries decoded Unicode without lossy ASCII
  coercion.

The same decoder feeds the adapter and base-subject extraction, preventing email
parser policy from changing thread grouping.

## Typed distribution — PEP 561

**PEP 561** (<https://peps.python.org/pep-0561/>) specifies the `py.typed` marker
for inline type information. CI verifies it in wheel and source distributions and
smoke-tests the installed wheel outside the source tree.

## Product and transport boundaries

Subject grouping is optional because distinct conversations can legitimately
share an exact base subject. Tree construction, extraction, comparison, ordering,
search projection, and response grammar are standards-grounded; deciding to
merge disconnected roots remains caller-selected.

ThreadWeave does not implement mailbox search execution, IMAP command parsing,
authentication, UIDVALIDITY lifecycle, persistence, or socket framing. Those are
server responsibilities. Keeping them separate lets the same core serve local
Python, naruon, migration services, archive viewers, and IMAP gateways.

## Provenance

The RFC 5322 header primitives (`normalize_message_id`,
`extract_reference_ids`, and `generate_email_fingerprint`) were extracted
behaviour-preserving from the naruon control plane. The threading, subject,
collation, date, and IMAP projection layers are fresh standalone implementations
designed to remain usable independently and as naruon modules.
