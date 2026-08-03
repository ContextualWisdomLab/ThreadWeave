# Research grounding

`threadweave` implements published standards and algorithms rather than an ad-hoc
mailbox heuristic. The primary sources and the implemented boundaries are below.

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
6. Return the resulting roots. Sent-date sorting and IMAP response serialization
   are not yet implemented because the transport-agnostic `Message` model does
   not currently require the relevant mailbox metadata.

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
2. Apply its Unicode titlecase mapping.
3. Recursively apply canonical or compatibility decomposition to the resulting
   code points — effectively Normalization Form KD.
4. Append the result and repeat for the remaining input.
5. Compare the prepared strings with octet equality/order semantics.

`unicode_casemap_key` performs steps 2-4 independently per Python code point
using `str.title()` and `unicodedata.normalize("NFKD", ...)`. RFC 5051 explicitly
permits an equivalent UTF-32 representation when all input is Unicode; Python
string comparison therefore provides a practical key representation after
preparation.

Consequences covered by tests include:

- ASCII case variants compare equally.
- Full-width compatibility forms compare with their ASCII equivalents.
- Precomposed and decomposed accents compare equally.
- RFC 5051's U+01C4/U+01C5/U+01C6 DZ-with-caron example produces
  `U+0044 U+007A U+030C` for every case form.
- Visual confusables from unrelated scripts remain different. For example,
  Latin `A` and Greek `Α` are not interchangeable.

RFC 5051 notes that results can vary across Unicode revisions as new characters
acquire titlecase or decomposition properties. `threadweave` therefore uses the
Unicode Character Database bundled with the active supported Python runtime and
documents the version boundary rather than hard-coding an obsolete table.

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

The remaining RFC 5256 transport-layer gap is sent-date sorting and IMAP
`THREAD` response serialization. Those require normalized Date/INTERNALDATE and
sequence-number metadata that the current generic `Message` model does not
mandate.

## Provenance

The RFC 5322 header primitives (`normalize_message_id`,
`extract_reference_ids`, and `generate_email_fingerprint`) were extracted
behaviour-preserving from the naruon control plane. The threading, subject, and
collation layers are fresh standalone implementations designed to remain usable
both independently and as naruon modules.
