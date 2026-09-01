# ThreadWeave Requirements and Evidence Traceability

**Status:** Accepted protected-main documentation baseline plus active release candidate  
**Last reviewed:** 2026-09-01

This matrix links durable product/technical requirements to standards, source boundaries, and evidence families. Exact test names may evolve; the governing invariant and its maturity must remain traceable.

| Requirement / decision | Primary basis | As-built source boundary | Evidence family | Maturity |
|---|---|---|---|---|
| PRD-FR-001 reference precedence | RFC 5256; RFC 5322 | `headers`, `threading` | reference-chain / In-Reply-To fallback tests | implemented-main |
| PRD-FR-002 dummy/pruning | JWZ; RFC 5256 | `container`, `threading` | missing-root, pruning, cycle/deep-chain tests | implemented-main |
| PRD-FR-003 subject normalization | RFC 5256 | `subject`, `threading` | base-subject + reply/forward + grouping tests | implemented-main |
| PRD-FR-004 Unicode comparison | RFC 5051 | `collation`, `subject` | Unicode/example/confusable regression tests | implemented-main |
| PRD-FR-005 sent-date ordering | RFC 5256 | `dates`, `threading` | timezone/date fallback/tie/dummy/bottom-up ordering tests | implemented-main |
| PRD-FR-006 IMAP projection | RFC 5256; RFC 9051 | `imap` | THREAD/UID/filter/dummy/deep/non-mutation/error tests | implemented-main |
| PRD-FR-007 stdlib adapter + mailbox authority | RFC 2047/5322/6532; RFC 5256 identifier semantics | `adapters`, `encoded_words`, `headers`, `imap`; protected-main PR #26 | iterable order stays internal; explicit host sequence/UID serialize; missing public ID fails closed | implemented-main |
| PRD-FR-008 determinism | product quality contract | all pure runtime modules | repeated-output, deep/cycle, packaging/CI suite | implemented-main |
| ADR-0001 canonical batch oracle | architecture decision | `threading`, `container` | batch structural suite | accepted/implemented |
| ADR-0002 transport-neutral core | architecture decision | runtime package + host boundary | no-runtime-dependency/package/API tests | accepted/implemented |
| ADR-0003 optional policies | compatibility + RFC behavior | `threading`, `subject`, `dates` | option-on/off tests | accepted/implemented |
| ADR-0004 incremental state | RFC 8474 + product scale target | PR #20 `incremental` | randomized batch parity, concurrency, snapshot, RFC 8474, benchmark tests | proposed/active-PR |
| ADR-0005 automation authority | supply-chain/security policy | `.github/workflows`, `scripts/ci` | secret isolation, patch guard, publisher/release boundary tests | accepted/implemented-main |
| ADR-0006 work-conserving maintenance | repository governance | protected-main hourly maintenance/development workflow + PR #28 | prompt contract and bounded publisher/model authority | accepted/implemented-main |
| ADR-0007 exact evidence identity | repository governance | PR/check/release evidence handling | contributor-head/base-snapshot/live-base/tested-ref assertions | accepted/implemented-main |
| ADR-0008 release publisher identity | GitHub Actions secret isolation; PyPI API-token / optional Trusted Publishing authority | PR #35 `.github/workflows/release.yml`, `docs/RELEASE_PROVENANCE.md` | protected-main/version/public-version preflight; boolean-only token availability; exact secret-expression allowlist; isolated pinned PyPA publisher; public digest/install proof | accepted/active-PR until #35 integrates; release incomplete until public 0.2.0 proof |
| ADR-0009 LineageWeave evidence-consumer boundary | RFC 8474 + cross-repository host boundary (`naruon#1437`, `LineageWeave#338`) | documentation only; no ThreadWeave runtime source change | product-gap dependency graph | proposed/documentation-only |
| ADR-0010 Actions registry lifecycle evidence | GitHub Actions/Git trees APIs + issue #31 | merged PR #32 detector/workflow | pagination, drift, identity/path classification, read-only authority, exact coverage/docstrings | accepted/implemented-main |
| data governance/privacy boundary | product governance | core no-I/O runtime + host boundary | no network/database/model I/O; payload/output boundary tests | accepted/implemented-main |
| incident/RCA ownership | repository operations | runtime + CI/release boundary | first-failing-layer RCA + regression + exact-head revalidation | accepted/implemented-main |
| release/provenance/licensing gate | release architecture | release workflow/package metadata/license | exact-head package hashes, SLSA/SPDX, immutable tag/release, isolated registry publisher, public digest + clean-install smoke | active release candidate; partial until first verified 0.2.0 public release |
| Python 3.14 compatibility | Python Software Foundation release line + CWL quality contract | protected-main PR #27; package metadata + CI matrix | Python 3.10–3.14 tests/coverage plus Python 3.14 package/hash-install/outside-source smoke | implemented-main |
| PEP 561 package typing | PEP 561 | package metadata / `py.typed` | wheel/sdist inclusion + external install smoke | implemented-main |
| zero runtime dependency | standalone architecture | package metadata | `pip check`, lock/build smoke | implemented-main |
| 100% production coverage/docstrings | CWL quality contract | all production modules | exact current-head coverage/docstring gates | implemented-main; re-prove every merge/release head |
| documentation reconstruction fitness | acquisition/readiness governance | canonical documentation graph | architecture documentation tests + gap baseline | implemented-main; reconcile on material release changes |

## Release authority trace

The first public `0.2.0` release is tracked by issue #17 and PR #35. The corrected release contract is:

```text
exact protected main
  → reviewed version + empty material Unreleased section
  → PyPI version-existence preflight
  → approved publisher availability (boolean only outside publisher)
  → build + exact quality gates
  → SLSA + SPDX attestations
  → annotated immutable tag
  → immutable GitHub Release
  → isolated pinned PyPA publish action receives PIPY_TOKEN
  → public PyPI filename/SHA-256 equality
  → clean-install THREAD/UID THREAD smoke
```

`PIPY_USERNAME` is not required by the selected API-token publisher and therefore is not materialized. Trusted Publishing remains an optional future publisher mode, not an external prerequisite for this release. No credential value is release evidence.

## Standards and authority source of truth

`docs/research/README.md` is the canonical protocol/research grounding and contains APA 7th references for JWZ, RFC 2047, RFC 5051, RFC 5256, RFC 5322, RFC 6532, RFC 9051, PEP 561, and the supported Python release line. Active incremental work additionally cites RFC 7162, RFC 8474, RFC 8621, and JSON where its snapshot/identity design requires them.

Release-identity implementation follows GitHub Actions secret/permission isolation, PyPI/PyPA package-publication contracts, and immutable package/version semantics. Product-specific package publication remains a ThreadWeave boundary while generic fleet changelog/tag/GitHub Release governance belongs to `ContextualWisdomLab/.github#1552`.

## Documentation maturity rules

- `implemented-main` means source exists on protected main and representative protected-main evidence exists.
- `accepted/active-PR` means an accepted decision is implemented on a current PR but must not be represented as protected-main/released behavior before integration.
- `proposed/active-PR` remains non-main product work.
- `partial until public release` means source/release mechanics may be integrated but the buyer-visible package is not considered released until public artifact proof succeeds.
- A queued, cancelled, stale, skipped, status-only, predecessor-head, or synthetic-only result does not advance maturity.

## Evidence identity rule

When merge/release correctness depends on repository state, record contributor head SHA, PR base snapshot SHA, independently resolved live protected-base tip, and tested checkout/merge-result identity separately. Evidence proves only the identity actually evaluated.

## Change rule

Every material PR updates the row(s) it changes. A feature must not move to `implemented-main` until its implementing commit is integrated and exact protected-head evidence exists. A package must not move to released maturity until the public registry artifact and its digest/install evidence are verified. Conversation-only decisions are not durable until captured in the owning code, ADR, workflow, or canonical documentation.
