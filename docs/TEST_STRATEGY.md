# ThreadWeave Test Strategy

**Status:** Accepted quality baseline  
**Last reviewed:** 2026-08-10

## Objective

Prove protocol/threading correctness, deterministic failure behavior, packaging integrity, runtime compatibility, and automation trust boundaries with realistic examples and exact coverage. Tests must measure product properties, not just implementation trivia.

## Mandatory gates

- production statement coverage: 100%;
- production branch coverage: 100%;
- authored production module/callable docstrings: 100%;
- Ruff;
- compileall;
- production doctests;
- full pytest suite;
- Python 3.10, 3.11, 3.12, 3.13, and 3.14 current-head lanes;
- dependency-lock integrity;
- wheel and sdist build where release workflow requires both;
- `py.typed` inclusion;
- Python 3.14 package build/hash-install and installed-wheel smoke from outside the repository source tree;
- GitHub Actions workflow syntax/security contracts;
- current-head SAST/security/review gates before merge.

A `requires-python` declaration or a predecessor-head run is not compatibility evidence. Changes to the dependency lock, build backend, supported-Python range, or package assembly must re-prove the full supported matrix and package smoke.

## Correctness layers

### Header and adapter tests

Cover valid and malformed RFC 5322 Message-ID, multi-ID References/In-Reply-To, RFC 2047 encoded words, unknown charset labels, Python `EmailMessage` objects, generators, duplicate identifiers, and payload ownership. Also prove that bulk iterable position remains internal ordering metadata and never becomes public sequence/UID authority.

### Canonical graph tests

Cover:

- simple parent/child chains;
- missing ancestor/dummy creation;
- branching siblings;
- reparenting and pruning;
- cyclic references;
- duplicate Message-ID behavior;
- deep chains without recursion failure;
- source object identity and structural non-aliasing where required.

### RFC 5256 subject tests

Use normative-style examples for reply/forward prefixes, mailing-list blobs, `(fwd)`, nested `[fwd: ...]`, repeated artifacts, empty subjects, and Unicode forms. Include cases proving unrelated same-subject messages are not merged when grouping is disabled.

### RFC 5051 collation tests

Cover ASCII case, full-width compatibility forms, composed/decomposed forms, simple-titlecase edge cases, ligatures/special casing, and visually confusable Latin/Greek/Cyrillic characters that must remain distinct.

### Sent-date ordering tests

Cover:

- valid timezone normalization;
- missing/invalid timezone policy;
- invalid time-to-midnight repair;
- `INTERNALDATE` fallback;
- unparseable/missing values;
- effective ordering-sequence uniqueness, including explicit/internal collisions;
- dummy-root first-child key;
- top-level and nested sibling ordering;
- subject-merge then bottom-up reordering;
- option-disabled backward compatibility;
- explicit proof that internal input-position fallback is never surfaced as an IMAP identifier.

### IMAP serialization tests

Cover ordinary and UID THREAD response shape, predicate filtering, excluded ancestors, dummy roots, custom identifier resolvers, empty results, duplicate/missing/out-of-range/bool identifiers, cycles/shared nodes, CRLF framing, deep chains, and source non-mutation.

## Real-world mailbox validity

Synthetic fixtures should mimic real historical mailbox defects without copying customer email. At minimum maintain mixed encodings, missing ancestors, delayed replies, repeated list prefixes, forwarded chains, duplicate IDs, timezone defects, and large/deep conversation shapes.

## Property and parity tests

Where practical, generate structurally valid random mailboxes and assert deterministic idempotence and structural invariants. Any incremental implementation must compare every applied transition with a complete canonical batch rebuild across randomized add/replace/remove sequences and every supported grouping/ordering option.

## Performance evidence

Benchmarks are acceptance evidence only when they also prove output parity. Record workload size, operation, affected-message count, wall time, retained/transient allocation where instrumented, peak RSS, runtime/tool version, and exact source commit. Avoid turning one benchmark number into a universal complexity claim.

## Active incremental target tests

If ADR-0004 is accepted, add/retain:

- optimistic version conflict tests;
- same-version concurrent writer tests;
- atomic rollback after validation/rebuild failure;
- stable caller-key replacement/expunge behavior;
- RFC 8474 identity consistency and disjoint namespaces;
- payload-free snapshot round-trip;
- exact schema-version/type checks;
- cyclic/aliased/non-plain/oversized snapshot rejection;
- bounded structural walk/record/byte limits;
- mailbox-scale incremental/full-rebuild digest parity.

Until that work lands on protected main, these are active-PR acceptance tests and not released-product evidence.

## Security and automation tests

Verify immutable GitHub Action refs, secret isolation, no model-to-publisher credential inheritance, bounded patch paths/modes/sizes, exact patch digest handoff, credential-free independent verification, and separation of development from approve/merge/release authority. Workflow tests must also preserve work-conserving continuation without allowing one autonomous run to publish multiple competing product PRs.

## Documentation contract tests

Tests should require canonical PRD, TRD, Architecture, UML, ERD/domain model, API contract, ADR index, Security, Threat Model, Data Governance, Test Strategy, Operability, Incident Runbook, Release/Provenance, Traceability, Documentation Audit, AGENTS, CLAUDE, README, and CHANGELOG. They should assert actual Markdown discoverability links, ADR status on the correct row, conceptual-vs-persisted ownership, current Python-support claims, exact evidence-identity terminology, and that active PR #20 is labelled as non-main target rather than current capability until merged.

## Failure policy

A skipped test required by a repository gate is not passing. A local result for a predecessor head is historical only. Flaky tests must be root-caused rather than retried until green. Tests may not rewrite production source at runtime to create a passing result. Synthetic merge evidence proves only the tested checkout identity and must not be mislabeled as contributor-head or protected-main evidence.

## Release verification

The final release candidate requires fresh protected-head Python 3.10–3.14 test/security/package evidence and artifact verification. A release must not reuse a PR-head wheel hash or a local-only run as authoritative release evidence. Public publication is complete only after the trusted-published artifact is independently fetched/installed and its version/provenance match the reviewed protected source.