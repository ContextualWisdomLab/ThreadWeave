# ADR-0003: Keep subject grouping and sent-date ordering explicit policies

**Status:** Accepted  
**Date:** 2026-08-09

## Context

RFC-grounded subject grouping and sent-date ordering are useful for protocol-compatible presentation, but changing historical defaults can reorder existing callers' results. Subject equality is also weaker evidence than explicit reference headers.

RFC 5256 `REFERENCES` threading is a six-step algorithm whose first structural
steps reconstruct parent/child edges from identification fields (Crispin &
Murchison, 2008; Resnick, 2008; Zawinski, 1997–2002). Subject gathering and
sent-date sorting are later, optional stages of that same algorithm:

- §2.1 requires a fixed base-subject extraction procedure after RFC 2047
  encoded-word decoding (Moore, 1996). A message is a reply or forward only when
  extraction removes a `subj-refwd`, `(fwd)` trailer, or `[fwd: ...]` wrapper.
  Removing a mailing-list blob alone does not classify the message.
- Subject comparison uses the RFC 5051 `i;unicode-casemap` preparation
  (simple titlecase from `UnicodeData.txt`, then compatibility decomposition)
  rather than locale-sensitive APIs or visual-confusable heuristics
  (Crispin, 2007). RFC 5051 is not locale-sensitive and warns that Latin `A`
  and Greek `Α` remain distinct.
- §2.2 defines sent-date recovery: adjust a valid RFC 5322 `Date` to UTC, treat
  an invalid or absent zone as UTC, treat an invalid time as `00:00:00`, fall
  back to mailbox `INTERNALDATE`, then the earliest representable UTC instant,
  and break exact ties with the mailbox sequence number. Dummy children are
  sorted before a dummy key is derived; after subject grouping, every sibling
  set is sorted bottom-up.

Those stages are standards-track presentation policy, not a replacement for
reference ancestry. Enabling them by default would silently merge unrelated
conversations that share a base subject and would reorder historical
first-appearance results.

## Decision

Reference threading remains authoritative. Subject fallback grouping is opt-in. RFC sent-date ordering is opt-in through `sort_by_sent_date`; first-appearance behavior remains the compatibility default. When ordering is enabled, the implementation uses the documented RFC 5256 date normalization/order rules. An explicit `sequence_number` is validated as a positive mailbox sequence number; when it is absent, the one-based input position is used only as an internal ordering fallback. The resulting effective ordering sequence values must be unique across all sorted messages. Input position is never inferred, exposed, or persisted as a public IMAP sequence number.

## Consequences

- Existing callers do not receive silent reordering or subject-based merging.
- Standards-compatible hosts can explicitly request the richer policy.
- Hosts that need public IMAP sequence-number serialization still supply and validate real mailbox identifiers at the presentation boundary; the ordering fallback does not create them.
- Tests must cover explicit sequence numbers, omitted-sequence fallback, duplicate effective values, both option states, and prove reference relationships are not weakened by subject grouping.
- Future default changes require a versioned compatibility decision and migration guidance.

## References

Crispin, M. (2007). *i;unicode-casemap - Simple Unicode Collation Algorithm*
(RFC 5051). RFC Editor. https://doi.org/10.17487/RFC5051

Crispin, M., & Murchison, K. (2008). *Internet Message Access Protocol—SORT and
THREAD extensions* (RFC 5256). RFC Editor. https://doi.org/10.17487/RFC5256

Moore, K. (1996). *MIME (Multipurpose Internet Mail Extensions) Part Three:
Message Header Extensions for Non-ASCII Text* (RFC 2047). RFC Editor.
https://doi.org/10.17487/RFC2047

Resnick, P. (Ed.). (2008). *Internet Message Format* (RFC 5322). RFC Editor.
https://doi.org/10.17487/RFC5322

Zawinski, J. (1997–2002). *Message threading*.
https://www.jwz.org/doc/threading.html
