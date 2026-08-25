# AGENTS.md — threadweave

Operating guide for automated agents working on this repository.

`threadweave` implements the JWZ container model with RFC 5256 `REFERENCES`
threading semantics, RFC 5322 identification-field parsing, RFC 2047 encoded-word
decoding, RFC 5256 base-subject extraction, RFC 5051 Unicode casemap comparison,
optional RFC 5256 sent-date ordering, RFC 5256 IMAP `THREAD` response
serialization, and atomic incremental mailbox indexing. Its value is correctness:
mail clients and ingestion systems rely on threading being deterministic,
standards-grounded, and impossible to hang on malformed input. Treat changes to
`threading.py`, `incremental.py`, `container.py`, `subject.py`, `collation.py`,
`dates.py`, `headers.py`, and `imap.py` as behavior-sensitive.

## Invariants that must not regress

1. **Loop safety.** No input may cause an infinite loop or recursive crash.
   Self-links, mutual reference cycles, malformed parent pointers, and cyclic
   child lists must terminate. Keep visited-set guards in every graph traversal.
2. **Reference-parent authority.** Link the complete valid `References` chain
   without stealing an existing good parent. When that chain is unavailable,
   RFC 5256 permits only the first valid `In-Reply-To` identifier as the parent.
   Never fabricate ancestry from later addresses or identifiers.
3. **Definitive reparenting is narrow.** A message's own effective references may
   replace a presumed parent only when the new edge cannot create a cycle.
4. **Empty-container pruning is exact.** Remove empty childless containers and
   splice-promote empty internal containers. At the root level, retain an empty
   container with multiple children as a missing-root grouping node; promote its
   sole child when it has exactly one.
5. **Subject behavior is standards-exact.** Decode RFC 2047 first; normalize RFC
   whitespace; handle reply/forward leaders, removable list blobs, `(fwd)`
   trailers, and `[fwd: ...]` wrappers. Compare resulting base subjects with RFC
   5051 `i;unicode-casemap`, not Python `casefold()`, locale-sensitive APIs, or
   visual-confusable heuristics. A dummy root remains the subject-table owner
   whenever one exists. A blob alone is not a reply or forward.
6. **Sent-date ordering follows both RFC stages.** When enabled, normalize `Date`
   to UTC, recover invalid zone/time components, fall back to `INTERNALDATE`, and
   then the earliest UTC instant. Sort top-level dummy children before deriving
   the dummy key; after subject grouping, sort every sibling set bottom-up.
7. **Mailbox sequence metadata is valid.** Exact sent-date ties use a unique
   positive sequence number. Omitted values use one-based input position, but an
   explicit value may not collide with that effective fallback.
8. **Missing roots become placeholders.** A referenced-but-unseen `Message-ID`
   yields an empty container that still co-threads its descendants.
9. **Duplicate Message-IDs survive.** A later distinct message with an already-
   seen identifier receives its own container; no payload is destroyed.
10. **Determinism and compatibility.** Without `sort_by_sent_date`, root and
    descendant order remains first appearance and child insertion order. Do not
    replace ordered structures with sets or silently change the default.
11. **Adapters preserve caller data.** The stdlib email adapter carries the source
    message as payload by default, preserves Unicode, tolerates damaged legacy
    encoded words, and carries `Date`, `INTERNALDATE`, sequence-number, and UID
    metadata supplied by the caller.
12. **IMAP projection is exact and non-mutating.** `THREAD` and `UID THREAD`
    output must use unique non-zero unsigned 32-bit identifiers, preserve RFC
    dummy-root grouping after search projection, reject cyclic or shared graphs,
    and leave the source `Container` tree unchanged. Rendering stays iterative,
    and response framing accepts only CRLF or a caller-owned empty suffix.
13. **Incremental updates remain batch-equivalent and atomic.** Immutable caller
    message keys—not sequence numbers—identify indexed records. Recompute every
    affected old/new reference or subject component through `thread_messages`,
    but do not pass unrelated components to the batch delegate. Validation or
    recomputation failure must leave records, version, roots, and projections
    unchanged. Snapshot state excludes arbitrary payloads and graph pointers.
14. **External identities follow RFC 8474.** `EMAILID` and `THREADID` use exact
    1–255 character ObjectID grammar, are case-sensitive, and use disjoint
    namespaces. Equal EMAILIDs require equal THREADIDs. Once a non-null value is
    reported, replacement cannot remove or change it; merges and splits remain
    explicit transitions rather than silent identity rewrites.

## Architecture and dependency rules

- Keep the runtime pure standard library unless a product requirement is both
  unavoidable and documented. Test/build-only dependencies are acceptable when
  justified.
- Preserve the standalone package API and its use as a naruon module. The header
  primitives originated in naruon; port behavioral fixes in both directions.
- Keep batch threading authoritative. The incremental layer owns caller keys,
  component bookkeeping, deltas, and payload-free snapshots; it must delegate
  every recomputed component to the existing batch engine rather than fork the
  threading algorithm.
- Keep IMAP response serialization separate from the transport-neutral batch,
  incremental, and date layers so non-IMAP callers do not inherit protocol state.
- Public behavior, compatibility aliases, typing markers, snapshot schemas, and
  external-ID handoff are release contracts. Record changes in `CHANGELOG.md`
  and update user/research docs.
- Unicode collation results depend on the Unicode Character Database bundled
  with the supported Python runtime. Tests must cover stable RFC examples and
  security-sensitive non-equivalences rather than version-specific new codepoints.

## Autonomous development loop

Hourly cadence, writer boundaries, NIM broker, and token setup are documented in
[`docs/operations/hourly-autonomous-maintenance.md`](docs/operations/hourly-autonomous-maintenance.md).

1. Open pull requests always take priority: inspect review threads and checks,
   make the smallest fixes, revalidate, merge only after the evidence is sound,
   then search again until the queue is empty.
2. When the queue is empty, select one highest-value buyer-visible gap. Work
   test-first and create exactly one bounded pull request. The product task must
   not merge or publish its own result; the maintenance loop owns that decision.
3. Maintain 100% production statement and branch coverage and complete authored
   production docstrings. Include adversarial and security-sensitive cases.
4. Avoid unrelated refactors, generated noise, skipped tests, and assertions that
   only duplicate implementation text. State standards sources and residual risk
   in the pull-request description.
5. Bump the semantic version and update `CHANGELOG.md` only when the package is
   genuinely releasable as that version.

## Verify

```bash
python -m pip install --require-hashes -r requirements/ci.lock
ruff check .
python -m compileall -q src tests scripts
python -m doctest \
  src/threadweave/collation.py \
  src/threadweave/dates.py \
  src/threadweave/headers.py \
  src/threadweave/subject.py
coverage run -m pytest -q
coverage report
python -m build --no-isolation
python -m pip check
```

Regenerate dependency policy only through `scripts/ci/compile_ci_lock.sh` with
uv 0.11.29, then review the complete lock diff and follow
[`docs/supply-chain.md`](docs/supply-chain.md). Never bypass a hash mismatch by
adding an unhashed install or re-enabling isolated build resolution.

For workflow changes, also parse every YAML file and run `bash -n` over every
shell `run` block. Built wheels must be installed and smoke-tested outside the
source tree.

## Code-owner review gates — disabled (on hold)

As of 2026-08-04, code-owner review requirements (`require_code_owner_reviews` in branch
protection, `require_code_owner_review` in rulesets) are disabled across the ContextualWisdomLab
org: there is a single maintainer (solo developer), so a code-owner approval gate can never be
satisfied. This is ON HOLD until the org has multiple maintainers — do NOT re-enable these
settings or add CODEOWNERS-based merge gates before then.
