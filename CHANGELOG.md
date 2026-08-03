# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

- Preserve root ordering when subject grouping creates a synthetic container.
- Preserve first-appearance root ordering for messages with missing or duplicate
  `Message-ID` values.
- Preserve insertion order during depth-first container traversal, exclude the
  traversal root from malformed cycles, and make re-adding a direct child
  idempotent.
- Compare mutable `Container` graph nodes by identity so cyclic structures are
  equality-safe and reparenting always removes the exact child instance.
- Accept raw `References` and `In-Reply-To` header strings, including multiple
  identifiers, in addition to already-split sequences.
- Follow RFC 5256 when `References` is unavailable by using only the first valid
  `In-Reply-To` identifier, and retain dummy containers as base-subject owners.
- Accept one-shot iterables in `thread_messages`.
- Add `message_from_email` and `thread_email_messages` adapters for Python's
  standard-library email objects while retaining each source object as payload.
- Add reusable `decode_header_text` RFC 2047 decoding for adapters and subject
  extraction.
- Decode RFC 2047 encoded words under both modern and legacy parser policies,
  recover unknown character sets best-effort, and retain malformed values
  instead of aborting mailbox ingestion.
- Implement exact RFC 5256 base-subject extraction, including mailing-list
  blobs, reply/forward leaders, `(fwd)` trailers, `[fwd: ...]` wrappers, and RFC
  whitespace normalization.
- Compare base subjects with RFC 5051 `i;unicode-casemap`, including Unicode
  titlecase mapping and recursive compatibility decomposition, instead of
  Python `casefold()`.
- Add public `unicode_casemap_key` preparation for standards-consistent equality
  and ordering keys while preserving unrelated-script confusables as distinct.
- Add explicit `is_reply_or_forward_subject` classification and retain
  `is_reply_subject` as a compatibility name with the standardized semantics.
- Add public `normalize_sent_date` normalization for RFC 5256 ordering: adjust
  valid dates to UTC, treat invalid zones as UTC and invalid times as midnight,
  fall back to `INTERNALDATE`, and use the earliest UTC instant when both values
  are unusable.
- Add `sent_date`, `internal_date`, and `sequence_number` metadata to `Message`.
- Add opt-in `sort_by_sent_date` processing for RFC 5256 steps 4 and 6, including
  top-level dummy-child ordering, first-child dummy keys, bottom-up sibling
  sorting, and sequence-number tie-breaking.
- Carry `Date`, `INTERNALDATE`, and sequence metadata through the standard-
  library email adapters; direct iterable order supplies deterministic one-based
  sequence numbers.
- Reject invalid or duplicate effective mailbox sequence numbers instead of
  silently producing contradictory ordering.
- Preserve decoded Unicode header values, including internationalized subjects,
  through the standard-library adapter.
- Require 100% production statement and branch coverage in CI and verify that
  every authored production callable carries a docstring.
- Build and smoke-test wheel/source distributions in CI, including verification
  that the PEP 561 `py.typed` marker is packaged.
- Add an hourly centralized review-fix/check-revalidation/merge workflow that
  delegates policy to the organization `.github` repository.
- Add a pull-request-first, single-flight hourly product-development dispatcher
  for the GitHub Agent Tasks public-preview API. It uses a supported fine-
  grained user token, the current API version, fail-closed task inventory, and
  contract tests that prevent self-merging or duplicate autonomous work.

## [0.1.0] - 2026-07-12

### Added
- Initial release of the canonical JWZ message-threading algorithm.
- `thread_messages(messages, *, group_by_subject=False)` — full JWZ assembly:
  id-table build, loop-safe `References` linking, root-set gathering, empty
  container pruning (with the root-level single-child special case), and
  optional base-subject grouping.
- `Message` input dataclass (`message_id`, `in_reply_to`, `references`,
  `subject`, `payload`) and loop-safe `Container` thread-tree node.
- RFC 5322 §3.6.4 primitives extracted behaviour-preserving from the naruon
  control plane: `normalize_message_id`, `extract_reference_ids`,
  `generate_email_fingerprint`.
- `normalize_subject` / `is_reply_subject` base-subject helpers.
- 27 tests covering linear chains, forks, missing roots, subject grouping,
  self- and mutual-reference loop resilience, duplicate Message-IDs, and the
  header primitives.
