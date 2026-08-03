# AGENTS.md — threadweave

Operating guide for automated agents working on this repository.

`threadweave` implements the JWZ container model with RFC 5256 `REFERENCES`
threading semantics, RFC 5322 identification-field parsing, RFC 2047 encoded-word
decoding, RFC 5256 base-subject extraction, and RFC 5051 Unicode casemap
comparison. Its value is correctness: mail clients and ingestion systems rely on
threading being deterministic, standards-grounded, and impossible to hang on
malformed input. Treat changes to `threading.py`, `container.py`, `subject.py`,
`collation.py`, and `headers.py` as behavior-sensitive.

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
6. **Missing roots become placeholders.** A referenced-but-unseen `Message-ID`
   yields an empty container that still co-threads its descendants.
7. **Duplicate Message-IDs survive.** A later distinct message with an already-
   seen identifier receives its own container; no payload is destroyed.
8. **Determinism.** Root and descendant order derives from first appearance and
   child insertion order. Do not replace ordered structures with sets.
9. **Adapters preserve caller data.** The stdlib email adapter carries the source
   message as payload by default, preserves Unicode, and tolerates damaged legacy
   encoded words without aborting ingestion.

## Architecture and dependency rules

- Keep the runtime pure standard library unless a product requirement is both
  unavoidable and documented. Test/build-only dependencies are acceptable when
  justified.
- Preserve the standalone package API and its use as a naruon module. The header
  primitives originated in naruon; port behavioral fixes in both directions.
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
  src/threadweave/headers.py \
  src/threadweave/subject.py
coverage run -m pytest -q
coverage report
python -m build
python -m pip check
```

For workflow changes, also parse every YAML file and run `bash -n` over every
shell `run` block. Built wheels must be installed and smoke-tested outside the
source tree.
