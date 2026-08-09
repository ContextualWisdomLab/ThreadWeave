# ThreadWeave Requirements and Evidence Traceability

**Status:** Accepted documentation baseline  
**Last reviewed:** 2026-08-09

This matrix links durable product/technical requirements to standards, source boundaries, and representative test/evidence families. Exact test names may evolve; the governing invariant must remain traceable.

| Requirement / decision | Primary basis | As-built source boundary | Evidence family | Maturity |
|---|---|---|---|---|
| PRD-FR-001 reference precedence | RFC 5256; RFC 5322 | `headers`, `threading` | reference-chain / In-Reply-To fallback tests | implemented-main |
| PRD-FR-002 dummy/pruning | JWZ; RFC 5256 | `container`, `threading` | missing-root, pruning, cycle/deep-chain tests | implemented-main |
| PRD-FR-003 subject normalization | RFC 5256 | `subject`, `threading` | base-subject + reply/forward + grouping tests | implemented-main |
| PRD-FR-004 Unicode comparison | RFC 5051 | `collation`, `subject` | UnicodeData/example/confusable regression tests | implemented-main |
| PRD-FR-005 sent-date ordering | RFC 5256 | `dates`, `threading` | timezone/date fallback/tie/dummy/bottom-up ordering tests | implemented-main |
| PRD-FR-006 IMAP projection | RFC 5256; RFC 9051 | `imap` | THREAD/UID/filter/dummy/deep/non-mutation/error tests | implemented-main |
| PRD-FR-007 stdlib adapter | RFC 2047/5322/6532 | `adapters`, `encoded_words`, `headers` | stdlib policy/charset/raw-reference tests | implemented-main |
| PRD-FR-008 determinism | product quality contract | all pure runtime modules | repeated-output, deep/cycle, packaging/CI suite | implemented-main |
| ADR-0001 canonical batch oracle | architecture decision | `threading`, `container` | batch structural suite | accepted/implemented |
| ADR-0002 transport-neutral core | architecture decision | runtime package + host boundary | no-runtime-dependency/package/API tests | accepted/implemented |
| ADR-0003 optional policies | compatibility + RFC behavior | `threading`, `subject`, `dates` | option-on/off tests | accepted/implemented |
| ADR-0004 incremental state | RFC 8474 + product scale target | PR #20 `incremental` | randomized batch parity, concurrency, snapshot, RFC 8474, benchmark tests | proposed/active-PR |
| ADR-0005 automation authority | supply-chain/security policy | `.github/workflows`, `scripts/ci` | secret isolation, patch guard, publisher/release boundary tests | accepted/implemented-main |
| PEP 561 package typing | PEP 561 | package metadata / `py.typed` | wheel/sdist inclusion + external install smoke | implemented-main |
| zero runtime dependency | standalone architecture | package metadata | `pip check`, lock/build smoke | implemented-main |
| 100% production coverage/docstrings | CWL quality contract | all production modules | coverage + `tests/test_documentation.py` | implemented-main |

## Standards source of truth

`docs/research/README.md` is the canonical research/standards grounding and contains APA 7th references and implemented-boundary explanations for JWZ, RFC 2047, RFC 5051, RFC 5256, RFC 5322, RFC 6532, RFC 9051, and PEP 561. Active incremental work additionally cites RFC 7162, RFC 8474, RFC 8621, and JSON where its snapshot/identity design requires them.

## Documentation maturity rules

- `implemented-main`: source exists on protected main and representative tests/evidence exist.
- `accepted/implemented`: an accepted ADR describes existing main behavior.
- `proposed/active-PR`: design exists in an open PR; it must not be represented as released/main functionality.
- A queued, cancelled, stale, skipped, or predecessor-head CI/review result does not advance maturity.

## Change rule

Every material PR should update the row(s) it changes or add a row when it introduces a new externally meaningful invariant. A feature must not move from `proposed/active-PR` to `implemented-main` until the implementing commit is integrated on protected main and exact protected-head verification exists.