# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

- Bound incremental snapshot size checks to streaming UTF-8 encoding and reject
  reused container identities so compact Python object graphs cannot trigger
  exponential JSON expansion or a second full serialized copy in memory.
- Reject cyclic built-in dictionaries and lists at the incremental snapshot
  restore boundary without recursion or unbounded traversal.
- Reject container and scalar subclasses plus non-plain-string object keys at
  the incremental snapshot restore boundary before sorted JSON encoding can
  invoke attacker-controlled iteration or comparison methods.
- Serialize every read and write on one `IncrementalThreadIndex` with a
  process-local reentrant lock so same-version concurrent writers yield one
  commit and one explicit conflict, while readers observe only committed state.
- Keep implicit RFC 5256 sent-date tie-break positions internal to the incremental
  engine instead of exposing invented IMAP sequence numbers on public roots.
- Return defensive structural copies from `IncrementalThreadIndex.roots` so caller
  graph edits cannot corrupt reusable index state while payload objects remain
  caller-owned references.
- Replace quadratic disconnected-component partitioning and pairwise thread-delta
  comparisons with bounded indexed passes, copy reverse-token buckets only when
  touched, and defer complete forest materialization until a caller requests it.
- Add deterministic 100,000-message incremental-versus-full-rebuild benchmark
  evidence with projection parity, affected-message counts, wall time, and peak RSS.
- Harden incremental snapshot publication and restore so schema versions require
  exact non-boolean integers and hostile nesting or unencodable Unicode fails
  closed with `IncrementalThreadError` instead of leaking runtime exceptions.

- Add an atomic `IncrementalThreadIndex` for mailbox additions, replacements,
  and removals with stable caller message keys, affected-component
  recomputation, batch-result parity, and explicit thread merge/split deltas.
- Add strict RFC 8474 `EMAILID` and `THREADID` handoff, including immutable
  values, exact ObjectID grammar, disjoint namespaces, and consistent THREADID
  values for equal EMAILIDs.
- Add versioned, bounded, JSON-safe incremental snapshots that omit arbitrary
  caller payloads and rebuild derived graph state through validated metadata.

## [0.2.0] - 2026-08-04

- Add iterative RFC 5256 `THREAD` and `UID THREAD` response serialization with
  search-result projection, sequence-number, UID, or callable identifier
  selection, dummy-root preservation, protocol-safe framing, and fail-closed
  graph and unsigned 32-bit identifier validation.
- Carry optional IMAP UID metadata through `Message` and `message_from_email`.
- Reject dot segments, encoded separators, nested escapes, path-parameter
  traversal, malformed percent escapes, and encoded controls in the loopback NIM
  broker before any request can reach the fixed upstream.
- Hash-lock every CI, test, lint, coverage, and build dependency, regenerate the
  universal lock byte-for-byte with a pinned uv compiler, and reuse the same
  reviewed toolchain in autonomous verification.
- Replace the unavailable Copilot Agent Tasks dispatcher with an hourly OpenCode
  development session backed by NVIDIA NIM.
- Keep the real `NVIDIA_NIM_API_KEY` outside the model process in a loopback-only
  credential broker that injects authorization only for the fixed NIM host,
  bounds traffic, strips caller credentials, and suppresses prompt logging.
- Isolate the model in a disposable `.git`-free workspace under an unprivileged
  user, with a non-secret placeholder provider key, no GitHub or OIDC credential,
  blocked undeclared network egress, bounded process resources, and no web-fetch
  tools; terminate surviving model descendants before trusted inspection.
- Add a fail-closed autonomous patch boundary that permits only bounded UTF-8
  text changes to product source, tests, docs, README, and CHANGELOG; reject
  workflow, policy, dependency, release, deletion, rename, link, binary,
  executable, mode, size, line-budget, unsafe metadata, and common secret-leak
  changes.
- Reapply the exact sealed patch on a fresh credential-free runner and require
  Ruff, compileall, doctests, the full pytest/coverage suite, package build,
  dependency checks, and installed-wheel smoke verification before a third fresh
  runner may open one PR with an external automation token.
- Require 100% statement and branch coverage for the autonomous patch guard and
  loopback NIM credential broker in addition to the package's production code.
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
