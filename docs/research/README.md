# Research grounding

`threadweave` implements published standards and algorithms rather than an ad-hoc
mailbox heuristic. The primary sources and implemented boundaries are below.

## Message threading — JWZ and RFC 5256 REFERENCES

- **Jamie Zawinski, “message threading”**
  (<https://www.jwz.org/doc/threading.html>) provides the influential container-
  based algorithm used by mature mail clients.
- **RFC 5256, “Internet Message Access Protocol — SORT and THREAD Extensions”**
  (<https://www.rfc-editor.org/rfc/rfc5256>) standardizes the `REFERENCES`
  threading algorithm.

The implemented reference-threading steps are:

1. Build an `id_table` mapping normalized `Message-ID` values to containers.
   Link `References` entries into a parent chain without loops and without
   overriding a container that already has a good parent.
2. When a usable `References` chain is absent, use the **first valid**
   `In-Reply-To` identifier as the message's only reference. RFC 5256 restricts
   the fallback because historical fields often contain addresses or ambiguous
   material after the first identifier.
3. Gather every container without a parent into the root set.
4. Prune dummy containers: remove empty leaves, splice-promote empty internal
   containers, and retain a multi-child dummy at the root as a missing-thread-
   root grouping node.
5. Optionally gather root threads by base subject. A dummy owner is retained
   whenever one exists; otherwise a non-reply/non-forward owner is preferred.
6. Optionally apply the RFC sent-date sorting stages described below.
7. Return the resulting roots as transport-neutral `Container` objects.

## Base-subject extraction — RFC 5256 §2.1 and §5

RFC 5256 requires a fixed seven-step procedure so clients produce consistent
base subjects. `normalize_subject` implements it:

1. Decode RFC 2047 encoded words; convert tabs and folded lines to spaces; and
   collapse repeated ASCII spaces.
2. Repeatedly remove trailing whitespace and `(fwd)` trailers.
3. Remove a leading `subj-leader`: optional mailing-list blobs followed by a
   case-insensitive `Re:`, `Fw:`, or `Fwd:` token, including the optional blob
   permitted between the token and colon.
4. Remove a leading `subj-blob` only when a non-empty base remains. A final blob
   may therefore be the complete subject.
5. Repeat leader and blob removal until stable.
6. Unwrap a surrounding `[fwd: ...]` form and restart from trailer removal.
7. Return the resulting text.

RFC 5256 classifies a message as a reply or forward when extraction removes a
`subj-refwd`, `(fwd)` trailer, or `[fwd: ...]` wrapper.
`is_reply_or_forward_subject` exposes that result. Removing a mailing-list blob
alone does not classify the message.

## Subject comparison — RFC 5051 i;unicode-casemap

RFC 5256 says subject comparisons are case-insensitive under its
internationalization rules. **RFC 5051, “i;unicode-casemap — Simple Unicode
Collation Algorithm”** (<https://www.rfc-editor.org/rfc/rfc5051>) defines the
required preparation and comparison:

1. Read one Unicode code point.
2. Apply its **simple titlecase mapping** from `UnicodeData.txt`. If no simple
   titlecase mapping exists, use its simple uppercase mapping; if neither exists,
   leave the code point unchanged.
3. Recursively apply canonical or compatibility decomposition to the resulting
   code point — effectively Normalization Form KD.
4. Append the result and repeat for the remaining input.
5. Compare the prepared strings with octet equality/order semantics.

Python's `str.title()` exposes the *full* titlecase mapping and can expand one
code point through `SpecialCasing.txt`; that is not the RFC 5051 operation. The
internal `_simple_titlecase` helper accepts a one-code-point `str.title()` result
but keeps the original code point when Python returns an expansion. For the
Unicode databases used by supported Python 3.10-3.13 runtimes, expanding full
mappings have no simple `UnicodeData.txt` titlecase/uppercase mapping.
`unicode_casemap_key` then applies `unicodedata.normalize("NFKD", ...)` to the
simple result. RFC 5051 permits an equivalent Unicode code-point representation,
so the prepared Python string is a practical equality and ordering key.

Consequences covered by tests include:

- ASCII case variants compare equally.
- Full-width compatibility forms compare with their ASCII equivalents.
- Precomposed and decomposed accents compare equally.
- RFC 5051's U+01C4/U+01C5/U+01C6 DZ-with-caron example produces
  `U+0044 U+007A U+030C` for every case form.
- Multi-code-point full case expansions are deliberately not substituted for
  simple mappings: `ß` remains `ß`, and the `ﬀ` ligature decomposes to lowercase
  `ff` rather than titlecase `Ff`.
- Visual confusables from unrelated scripts remain different. For example,
  Latin `A` and Greek `Α` are not interchangeable.

RFC 5051 notes that results can vary across Unicode revisions as new characters
acquire titlecase or decomposition properties. `threadweave` therefore uses the
Unicode Character Database bundled with the active supported Python runtime and
documents the version boundary rather than hard-coding an obsolete table.

## Sent-date ordering — RFC 5256 §2.2 REFERENCES steps 4 and 6

RFC 5256 does not leave date recovery or sibling ordering to implementation
preference. `normalize_sent_date` and `sort_by_sent_date=True` implement these
rules:

1. Parse the message's RFC 5322 `Date` and adjust a valid value to UTC.
2. Treat an invalid or absent zone as UTC.
3. Treat an invalid time as `00:00:00` in the recovered local zone.
4. If `Date` is missing or cannot provide a calendar date, use mailbox
   `INTERNALDATE`.
5. If neither value is usable, use the earliest representable UTC instant.
6. Break exact sent-date ties with the positive mailbox sequence number.
7. Before subject grouping, sort top-level roots. For a top-level dummy, first
   sort its children and use its first child's key as the dummy key.
8. After subject grouping, sort every sibling set bottom-up so grandchildren are
   ordered before their parent is compared as part of an ancestor sibling set.

`DateValue` accepts an already parsed `datetime` or RFC-style text. Naive
`datetime` values follow the invalid-zone rule and are interpreted as UTC. RFC
5322 permits a leap second value of `60`; Python's `datetime` cannot represent
that second directly, so the implementation uses the final microsecond before
the following minute, preserving its ordering after second `59` and before the
next minute.

Ordering is opt-in to preserve the package's historical first-appearance order.
When enabled, omitted sequence numbers use one-based input position. All
effective sequence numbers must be unique positive integers; mixed explicit and
implicit metadata that collides is rejected instead of producing a false RFC
tie-break.

The stdlib adapter reads the decoded `Date` header. `message_from_email` also
accepts server-provided `internal_date` and `sequence_number`; the convenience
`thread_email_messages` adapter uses iterable order as sequence number when
threading a mailbox directly.

## IMAP THREAD response encoding — RFC 5256 §4 and RFC 9051

RFC 5256 defines `thread-data` as `THREAD` followed by zero or more
parenthesized `thread-list` values. Successive numbers identify a parent-child
chain. When a node has sibling subthreads, each branch becomes its own nested
list. The published example therefore serializes as:

```text
* THREAD (2)(3 6 (4 23)(44 7 96))
```

`serialize_thread_data` and `serialize_thread_response` implement that grammar
as a presentation layer over the transport-neutral tree:

1. Use message sequence numbers for ordinary `THREAD`, UIDs for `UID THREAD`, or
   a caller-supplied resolver when mailbox identifiers are stored externally.
2. Apply an optional server search-result predicate before rendering. Excluded
   concrete ancestors and dummy internal containers are splice-promoted. A
   top-level excluded or missing ancestor with multiple selected branches is
   retained as the grouping form `((3)(5))`.
3. Require every emitted identifier to be a unique non-zero unsigned 32-bit
   integer. RFC 9051 retains this `nz-number` boundary and identifies UIDs as
   non-zero unsigned 32-bit values.
4. Reject cycles, shared containers, malformed node types, duplicate identifiers,
   missing UIDs, and protocol-unsafe line endings rather than truncating output.
5. Render chains and arbitrarily deep sibling splits iteratively. RFC 5256 places
   no nesting limit on THREAD responses, so recursion depth cannot be a product
   limit.
6. Leave the source `Container` graph unchanged. Search projection is an
   ephemeral response view, not a mutation of the canonical conversation tree.

RFC 9051 specifies IMAP4rev2 framing as CRLF-terminated protocol lines and states
that registered IMAP4rev1 extensions remain valid for IMAP4rev2 unless an
extension says otherwise. RFC 5256 therefore remains the standards-track source
for the SORT and THREAD extension while RFC 9051 supplies the current base IMAP
number and framing contract.

## Identification fields — RFC 5322 §3.6.4

- **RFC 5322, “Internet Message Format”, §3.6.4 (Identification Fields)**
  (<https://www.rfc-editor.org/rfc/rfc5322#section-3.6.4>) defines `Message-ID`,
  `In-Reply-To`, `References`, and the `msg-id` grammar.
- Both reply-reference fields can contain one or more identifiers. The public
  model accepts either raw header text or already-split sequences. Parsing keeps
  first appearance and removes duplicates; the threading layer applies RFC
  5256's first-valid-only rule specifically to the `In-Reply-To` fallback.
- Angle brackets are stripped and malformed-but-recoverable whitespace-delimited
  values are tolerated at ingestion.

## Encoded words — RFC 2047

- **RFC 2047, “Message Header Extensions for Non-ASCII Text”**
  (<https://www.rfc-editor.org/rfc/rfc2047>) defines MIME encoded words such as
  `=?utf-8?b?...?=`.
- Modern email policies often decode these transparently, while legacy
  `compat32` can expose the transport representation. `decode_header_text`
  explicitly decodes encoded words, preserves ordinary interstitial text,
  recovers unknown character-set labels with replacement decoding, and retains
  malformed encoded words verbatim rather than rejecting the whole message.
- The same primitive feeds the stdlib adapter and base-subject extraction so
  parser policy cannot alter grouping behavior.

## Internationalized headers — RFC 6532

- **RFC 6532, “Internationalized Email Headers”**
  (<https://www.rfc-editor.org/rfc/rfc6532>) permits UTF-8 in most header values.
  The adapter carries decoded Unicode text without lossy ASCII coercion.

## Typed-package distribution — PEP 561

- **PEP 561, “Distributing and Packaging Type Information”**
  (<https://peps.python.org/pep-0561/>) specifies the `py.typed` marker for
  packages with inline type information. CI verifies the marker in wheel and
  source distributions.

## Heuristic and transport boundaries

Subject grouping is optional because distinct conversations can legitimately
share the exact same standardized base subject. The extraction and comparison
procedures are standards-grounded; deciding to merge disconnected roots remains
a caller-selected heuristic (`group_by_subject=False` by default).

Sent-date sorting and IMAP THREAD serialization are implemented, but remain
explicit opt-in presentation and ordering layers. The core `Container` graph has
no socket, command parser, session, authentication, or capability-advertisement
state. This boundary lets the same tree serve local Python, naruon, IMAP4rev1,
IMAP4rev2, and non-IMAP services.

## Provenance

The RFC 5322 header primitives (`normalize_message_id`,
`extract_reference_ids`, and `generate_email_fingerprint`) were extracted
behaviour-preserving from the naruon control plane. The threading, subject,
collation, date, and protocol-projection layers are fresh standalone
implementations designed to remain usable both independently and as naruon
modules.

## References (APA 7th edition)

Crispin, M., & Murchison, K. (2008). *Internet Message Access Protocol—SORT and
THREAD extensions* (RFC 5256). RFC Editor. <https://doi.org/10.17487/RFC5256>

Melnikov, A., & Leiba, B. (Eds.). (2021). *Internet Message Access Protocol
(IMAP)—Version 4rev2* (RFC 9051). RFC Editor.
<https://doi.org/10.17487/RFC9051>
