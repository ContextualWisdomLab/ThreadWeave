# ThreadWeave Release, Provenance, and Licensing Gate

**Status:** Accepted release-readiness guidance  
**Last reviewed:** 2026-09-01

A merge is not a release. ThreadWeave release completion requires one exact integrated protected head, reproducible package evidence, independent policy gates, an explicitly approved publisher identity, and post-publication verification.

## Release authority

Separate these authorities:

1. development proposes source changes;
2. deterministic CI proves tests, coverage, package integrity, and static gates;
3. independent reviewers/security gates review the exact head;
4. protected-branch policy permits integration;
5. the `release-readiness` gate resolves the reviewed package version, confirms protected-main authority, verifies the target is not already public, and proves an approved publisher mode is available before irreversible release work;
6. the release workflow builds from the integrated protected head and produces one immutable release evidence bundle;
7. the isolated registry publisher receives only the credential needed for its selected publisher mode;
8. post-publication verification proves the public artifact corresponds byte-for-byte to the reviewed release bundle and remains installable.

The development model must never approve, merge, tag, or publish its own output.

## Exact-head release checklist

Before release:

- version metadata and `CHANGELOG.md` agree;
- `## Unreleased` contains no material notes that would be omitted from the final version;
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

## Changelog-driven readiness preflight

ADR-0008 requires release authority to fail closed before build, attestation, tag creation, or GitHub Release creation when a new public version is required but no approved registry publisher is available.

The preflight must verify:

- execution is bound to exact protected `main` in `ContextualWisdomLab/ThreadWeave`;
- the reviewed `[project].version` is one canonical `MAJOR.MINOR.PATCH` value;
- a manual recovery version, when supplied, equals the reviewed project version;
- PyPI does not already contain that version before a new release begins;
- the approved organization secret `PIPY_TOKEN` is available when the API-token publisher mode is selected;
- secret presence is represented only as a boolean readiness fact outside the publisher job;
- missing publisher authority or unexpected PyPI responses fail closed.

A protected-main push affecting `CHANGELOG.md`, package version metadata, the release contract, or the release workflow may start this preflight automatically. If the reviewed version already exists on PyPI, the workflow records a no-op rather than attempting to overwrite an immutable public version. `workflow_dispatch` remains an idempotent recovery entry point; it is not a second release authority.

## Approved PyPI publisher modes

ThreadWeave recognizes two registry-authentication modes:

### GitHub-secret API token

The currently approved production path uses the organization GitHub Secret named exactly `PIPY_TOKEN`. The pinned `pypa/gh-action-pypi-publish` action receives it only as its `password` input, relying on the action's PyPI API-token username default (`__token__`). `PIPY_USERNAME` exists at the organization level but is not materialized because this publisher does not require it.

The token value must never appear in shell commands, logs, workflow outputs, cache keys, artifacts, SBOM/provenance payloads, release notes, or release receipts. Build, test, attestation, tag, GitHub Release, and post-publication verification jobs must not receive the token.

### Trusted Publishing

PyPI Trusted Publishing remains a preferred future credential-minimization path when its account-side OIDC relationship is configured and accepted. It is not a prerequisite while the approved secret-backed API-token publisher is available. A future migration to Trusted Publishing must be a reviewed publisher-mode change; the workflow must not silently fall back between credential modes after an authentication or publication failure.

Using `PIPY_TOKEN` through the reviewed isolated publisher is not a bypass. What remains prohibited is introducing ad-hoc credentials, manual workstation uploads, unreviewed publisher code, skipped digest/provenance checks, rewritten tags, or weakened exact-head/review/security gates merely to force publication.

## Artifact identity

Record at minimum:

- protected commit SHA;
- package version;
- wheel filename + SHA-256;
- sdist filename + SHA-256;
- SBOM/provenance/attestation identifiers where generated;
- release/tag identifier;
- CI/security/review run identities;
- publisher mode name, but never credential material;
- publication timestamp and public package location;
- post-publication clean-install smoke result.

Never infer artifact identity from a mutable branch name.

## Public-artifact verification

After publication, the workflow must fetch the public PyPI metadata for the exact version and compare the wheel/sdist filename and SHA-256 set against the reviewed `SHA256SUMS.txt`. Only then may it create a clean environment, install `threadweave==<version>` from PyPI, and reproduce representative `THREAD` and `UID THREAD` serialization behavior. A successful upload without this public-artifact proof is not release completion.

## Rollback and re-release

- Prefer a new patch release for corrected published artifacts; do not silently replace immutable public artifacts.
- Preserve the last known-good public version and its evidence.
- A readiness failure must create no tag/GitHub Release side effects.
- A later failure after attestation/tag/release must use the workflow's idempotent verification/recovery path rather than deleting or rewriting immutable evidence.
- If PyPI publication succeeds but a later public-artifact verification step fails, investigate the public artifact and retry verification; never republish the same immutable filename/version.
- A runtime rollback normally means selecting the last known-good package version because protected-main ThreadWeave owns no persistence.
- If a future snapshot schema becomes public, snapshot compatibility and recovery become part of the release gate before publication.

## Licensing

The repository currently uses Apache-2.0. Distribution must preserve the repository `LICENSE` and any third-party notices/license obligations introduced by future vendored/generated content or dependencies.

Because the current runtime is zero-dependency, third-party runtime-license exposure is intentionally minimal. Build/test tools are still supply-chain inputs and must remain pinned/reviewed; adding a runtime dependency requires an ADR and a license/security review.

A future `NOTICE` file should be added only when an actual attribution/notice obligation or repository policy requires it; do not create a misleading empty legal artifact solely to satisfy a checklist.

## Release notes

Release notes must disclose compatibility-significant fail-closed changes even when they are technically bug fixes, including tighter validation of identifiers, graph state, Unicode assumptions, ordering metadata, serialized protocol state, or publication authority.

## Completion rule

A release is complete only after the public artifact is discoverable, its hashes/provenance correspond to the intended protected head, a clean environment can install it, representative `THREAD`/`UID THREAD` smoke behavior passes, and the release-blocker record is reconciled. After that event, immediately refetch open PRs/issues and continue the product loop.
