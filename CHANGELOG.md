# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## [0.2.0] - 2026-09-01

- Replace the previously OIDC-only PyPI prerequisite with the approved
  organization `PIPY_TOKEN` publisher path. The pinned PyPA action receives the
  token only in its isolated publication job; build, attestation, tag, GitHub
  Release, release-receipt, cache, and shell steps never receive the secret.
  Trusted Publishing remains an optional future credential-minimization path,
  not a prerequisite for this release.
- Make release execution changelog/version-driven from exact protected `main`
  only after the repository `ci` workflow completes successfully. The release
  authority revalidates the integrated source SHA, integrated CI/SAST evidence,
  and the merged source PR's CI/SAST/Security evidence before build or immutable
  release side effects. Stale or already-public automatic invocations are
  successful no-ops, while manual dispatch remains an exact-main idempotent
  recovery and verification path.
- Add fail-closed partial-publication recovery: rebuild the reviewed wheel/sdist,
  compare every already-public PyPI filename and SHA-256 before attestation/tag
  side effects, upload only matching missing distributions without
  `skip-existing`, and retry only bounded normal registry propagation.
- Add post-publication verification that compares the complete PyPI wheel/sdist
  SHA-256 set with the reviewed release bundle before a clean public install and
  `THREAD`/`UID THREAD` smoke test can mark release completion.
- Keep the root README a customer/operator guide for standalone
  `pip install threadweave` and host composition through
  `from threadweave import thread_messages`, and move the hourly autonomous
  maintenance playbook to
  [`docs/operations/hourly-autonomous-maintenance.md`](docs/operations/hourly-autonomous-maintenance.md).
- Add [`docs/product-technical-gap-baseline.md`](docs/product-technical-gap-baseline.md)
  tracking every open PR/issue's exact blocking dependency and the confirmed
  cross-repository LineageWeave/naruon evidence-consumption chain
  (`naruon#1437` → `naruon#1350` → this repository's PR #20 stable-identity
  contract → `LineageWeave#338`), and record ADR-0009 documenting that
  ThreadWeave stays unaware of LineageWeave — naruon owns the projection.
- Add a read-only GitHub Actions registry lifecycle audit
  (`scripts/ci/actions_registry_audit.py`) that classifies every live
  workflow identity as backed by protected-main source, a current open-PR
  head, disabled, GitHub-owned/dynamic, a confirmed orphan, or unresolved,
  closing the evidence gap from issue #31 without granting the detector any
  workflow-disable authority. Run it on protected-main changes to the
  detector, on manual dispatch, and hourly at minute 53 through
  `.github/workflows/actions-registry-audit.yml` with exactly
  `actions: read`, `contents: read`, and `pull-requests: read` — not on pull
  requests, since the audit is meant to fail visibly on a genuine live
  orphan and running it there would make it a permanently red check on
  every unrelated PR for as long as any real orphan remains undisabled.
  `tests/test_actions_registry_audit.py` provides exact 100%
  statement/branch coverage of the detector itself in `ci.yml`'s existing
  PR-time gate. See ADR-0010.
- Extend the canonical architecture graph with a reconstruction-oriented
  documentation fitness audit, data-governance/privacy boundary, incident/RCA
  runbook, release/provenance/licensing gate, work-conserving autonomous
  maintenance ADR, and exact evidence-identity ADR.
- Restore `CLAUDE.md` as canonical agent context, explicitly preserving the
  OpenCode + `NVIDIA_NIM_API_KEY` development boundary, prohibiting Copilot-token
  use for development-model execution, and recording the protected-main Python
  3.10–3.14 compatibility contract.
- Add Python 3.14 to package classifiers and the full CI matrix, and build,
  hash-install, and smoke-test the distribution under Python 3.14 while
  preserving Python 3.10 as the minimum supported runtime.
- Add a canonical product/technical architecture documentation graph with PRD,
  TRD, root architecture, UML, conceptual ERD, API/version contract, indexed
  ADRs, security/threat model, data governance, test strategy, operability,
  incident/recovery, release provenance, traceability, and machine-checkable
  documentation maturity guards that distinguish protected-main behavior from
  active PR #20 incremental-state work.
- Restore the hourly NVIDIA NIM/OpenCode product-development workflow's YAML and
  nested-shell contracts, and lint every GitHub Actions workflow with a pinned,
  checksum-verified `actionlint` release before ordinary CI may proceed.
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
- Carry `Date` plus explicitly supplied `INTERNALDATE`, sequence-number, and UID
  metadata through `message_from_email`; `thread_email_messages` leaves public
  sequence/UID metadata unset and relies on the canonical threader's one-based
  input position only as an internal deterministic sent-date ordering fallback.
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
