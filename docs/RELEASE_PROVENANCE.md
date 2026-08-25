# ThreadWeave Release, Provenance, and Licensing Gate

**Status:** Accepted release-readiness guidance  
**Last reviewed:** 2026-08-10

A merge is not a release. ThreadWeave release completion requires one exact integrated protected head, reproducible package evidence, independent policy gates, trusted publication, and post-publication verification.

## Release authority

Separate these authorities:

1. development proposes source changes;
2. deterministic CI proves tests, coverage, package integrity, and static gates;
3. independent reviewers/security gates review the exact head;
4. protected-branch policy permits integration;
5. the `release-readiness` gate proves the repository-side deployment environment exists with reviewed protection before irreversible release work;
6. the release workflow builds from the integrated protected head;
7. Trusted Publishing/environment policy authorizes publication;
8. post-publication verification proves the public artifact corresponds to the intended release.

The development model must never approve, merge, tag, or publish its own output.

## Exact-head release checklist

Before release:

- version metadata and `CHANGELOG.md` agree;
- Python support metadata agrees with the actual Python 3.10–3.14 protected-main CI matrix;
- production statement and branch coverage are exactly 100%;
- authored production public docstrings satisfy the repository contract;
- Ruff, compileall, doctests, full pytest, dependency integrity, and workflow syntax gates pass;
- Security Scan and SAST pass;
- required independent review is current for the same release head;
- wheel and source distribution are freshly built from that head;
- `py.typed`, license files, metadata, and package contents are verified;
- the wheel is hash-installed and smoke-tested outside the source tree;
- SBOM/provenance/attestation steps configured by the release workflow pass;
- tag and GitHub Release identities match the package version and protected commit.

## Repository-side release-readiness preflight

ADR-0008 requires the manual release workflow to fail before build, attestation, tag creation, or GitHub Release creation unless the repository-side Trusted Publishing boundary is already prepared.

The preflight must verify:

- the requested version is canonical `MAJOR.MINOR.PATCH` before external lookup;
- a GitHub environment named `pypi` is **pre-created**, consistent with GitHub's documented environment prerequisite, so a missing environment is detected before the late publishing job;
- the environment has at least one required reviewer;
- self-review is prevented;
- deployment is restricted to protected branches;
- the requested ThreadWeave version is not already present on PyPI;
- missing/unreadable environment state or unexpected GitHub/PyPI responses fail closed.

This preflight proves only the repository/GitHub half of the publication boundary. It cannot truthfully prove the PyPI account-side Trusted Publisher relationship before OIDC token exchange/publication, so that external evidence remains an explicit acceptance item. The environment-bound `publish-pypi` job still enforces the actual required-reviewer approval before publication authority becomes available.

## Trusted publication boundary

Do not introduce a long-lived PyPI token or manual artifact upload to bypass failed OIDC/Trusted Publishing, environment policy, identity claims, digest checks, provenance, or approval requirements. Account-side configuration is an external authority boundary and remains an explicit release blocker until end-to-end evidence exists.

For the first `0.2.0` publication, issue #17 or its successor is the acceptance record. Repository source readiness alone does not close that boundary. The PyPI publisher claims must bind owner `ContextualWisdomLab`, repository `ThreadWeave`, workflow `release.yml`, and environment `pypi`.

## Artifact identity

Record at minimum:

- protected commit SHA;
- package version;
- wheel filename + SHA-256;
- sdist filename + SHA-256;
- SBOM/provenance/attestation identifiers where generated;
- release/tag identifier;
- CI/security/review run identities;
- publication timestamp and public package location;
- post-publication clean-install smoke result.

Never infer artifact identity from a mutable branch name.

## Rollback and re-release

- Prefer a new patch release for corrected published artifacts; do not silently replace immutable public artifacts.
- Preserve the last known-good public version and its evidence.
- A preflight failure must create no tag/GitHub Release side effects.
- A later failure after attestation/tag/release must use the workflow's idempotent verification/recovery path rather than deleting or rewriting immutable evidence.
- A runtime rollback normally means selecting that known-good package version because protected-main ThreadWeave owns no persistence.
- If a future snapshot schema becomes public, snapshot compatibility and recovery become part of the release gate before publication.

## Licensing

The repository currently uses Apache-2.0. Distribution must preserve the repository `LICENSE` and any third-party notices/license obligations introduced by future vendored/generated content or dependencies.

Because the current runtime is zero-dependency, third-party runtime-license exposure is intentionally minimal. Build/test tools are still supply-chain inputs and must remain pinned/reviewed; adding a runtime dependency requires an ADR and a license/security review.

A future `NOTICE` file should be added only when an actual attribution/notice obligation or repository policy requires it; do not create a misleading empty legal artifact solely to satisfy a checklist.

## Release notes

Release notes must disclose compatibility-significant fail-closed changes even when they are technically bug fixes, including tighter validation of identifiers, graph state, Unicode assumptions, ordering metadata, serialized protocol state, or publication readiness.

## Completion rule

A release is complete only after the public artifact is discoverable, its hashes/provenance correspond to the intended protected head, a clean environment can install it, representative `THREAD`/`UID THREAD` smoke behavior passes, and the release-blocker record is reconciled. After that event, immediately refetch open PRs/issues and continue the product loop.