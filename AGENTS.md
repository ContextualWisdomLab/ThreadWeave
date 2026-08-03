# AGENTS.md — threadweave

Operating guide for automated agents working on this repository.

`threadweave` implements the JWZ container model with RFC 5256 `REFERENCES`
threading semantics, RFC 5322 identification-field parsing, RFC 2047 encoded-word
decoding, RFC 5256 base-subject extraction and sent-date ordering, RFC 5051
Unicode casemap comparison, and IMAP `THREAD` response serialization. Its value
is correctness: mail clients and ingestion systems rely on deterministic,
standards-grounded behavior that cannot hang on malformed input. Treat changes to
`threading.py`, `container.py`, `subject.py`, `collation.py`, `dates.py`,
`headers.py`, and `imap.py` as behavior-sensitive.

## Invariants that must not regress

1. **Loop safety.** No input may cause an infinite loop or recursive crash.
   Self-links, mutual reference cycles, malformed parent pointers, cyclic child
   lists, shared nodes, and deep chains must terminate or fail explicitly.
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
   visual-confusable heuristics. A dummy root remains the subject-table owner.
6. **Sent-date ordering follows both RFC stages.** When enabled, normalize `Date`
   to UTC, recover invalid zone/time components, fall back to `INTERNALDATE`, and
   then the earliest UTC instant. Sort top-level dummy children before deriving
   the dummy key; after subject grouping, sort every sibling set bottom-up.
7. **Mailbox metadata is valid.** Exact sent-date ties use a unique positive
   sequence number. IMAP response identifiers are unique non-zero unsigned
   32-bit integers. UID output must not fall back silently to sequence numbers.
8. **Missing roots become placeholders.** A referenced-but-unseen `Message-ID`
   yields an empty container that still co-threads its descendants.
9. **Duplicate Message-IDs survive.** A later distinct message with an already-
   seen identifier receives its own container; no payload is destroyed.
10. **Determinism and compatibility.** Without `sort_by_sent_date`, root and
    descendant order remains first appearance and child insertion order. Do not
    replace ordered structures with sets or silently change the default.
11. **Adapters preserve caller data.** The stdlib email adapter carries the source
    message as payload by default, preserves Unicode, tolerates damaged legacy
    encoded words, and carries `Date`, `INTERNALDATE`, sequence, and UID metadata.
12. **THREAD projection is non-mutating.** Search-result projection may omit an
    ancestor while retaining matching descendants, but it must never rewrite
    source parents, children, messages, or ordering.
13. **THREAD grammar is exact.** Concrete parent-child chains use successive
    numbers; sibling splits use nested thread-lists; an identifier-less dummy is
    valid only at the top level and only with at least two branches. Empty output
    is exactly `THREAD` or `* THREAD\r\n`.
14. **Protocol output fails closed.** Reject invalid graph nodes, cycles, shared
    containers, duplicate or out-of-range identifiers, invalid dummy placement,
    and arbitrary response suffixes. Never truncate or guess a malformed tree.

## Architecture and dependency rules

- Keep the runtime pure standard library unless a product requirement is both
  unavoidable and documented. Test/build-only dependencies are acceptable when
  justified.
- Preserve the standalone package API and its use as a naruon module. The header
  primitives originated in naruon; port behavioral fixes in both directions.
- Keep IMAP response projection separate from command parsing, mailbox search,
  persistence, authentication, UIDVALIDITY, and socket framing.
- Public behavior, compatibility aliases, and typing markers are release
  contracts. Record changes in `CHANGELOG.md` and update user/research docs.
- Unicode collation results depend on the Unicode Character Database bundled
  with the supported Python runtime. Tests must cover stable RFC examples and
  security-sensitive non-equivalences rather than version-specific new codepoints.

## Autonomous development loop

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
python -m pip install -e ".[test]" ruff build
ruff check .
python -m compileall -q src tests
python -m doctest \
  src/threadweave/collation.py \
  src/threadweave/dates.py \
  src/threadweave/headers.py \
  src/threadweave/subject.py
coverage run -m pytest -q
coverage report
python -m build
python -m pip check
```

Built wheels must be installed and smoke-tested outside the source tree. For
workflow changes, also parse every YAML file and run `bash -n` over every shell
`run` block.
