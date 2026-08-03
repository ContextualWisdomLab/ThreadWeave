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
- Accept one-shot iterables in `thread_messages`.
- Add `message_from_email` and `thread_email_messages` adapters for Python's
  standard-library email objects while retaining each source object as payload.
- Decode RFC 2047 encoded words under both modern and legacy parser policies,
  recover unknown character sets best-effort, and retain malformed values
  instead of aborting mailbox ingestion.
- Preserve decoded Unicode header values, including internationalized subjects,
  through the standard-library adapter.
- Require 100% production statement and branch coverage in CI and verify that
  every authored production callable carries a docstring.
- Build and smoke-test wheel/source distributions in CI, including verification
  that the PEP 561 `py.typed` marker is packaged.

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
