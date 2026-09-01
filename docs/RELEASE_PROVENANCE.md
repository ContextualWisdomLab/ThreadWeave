# ThreadWeave Release, Provenance, and Licensing Gate

**Status:** Accepted release-readiness guidance  
**Last reviewed:** 2026-09-01

A merge is not a release. ThreadWeave release completion requires one exact integrated protected head, terminal-success release authority, reproducible package evidence, an explicitly approved publisher identity, immutable release evidence, and post-publication verification.

## Release authority

Separate these authorities:

1. development proposes source changes;
2. deterministic CI/security workflows prove the exact contributor and integrated identities;
3. independent review and protected-branch policy authorize integration;
4. the repository `ci` workflow completes successfully for `main` and supplies the candidate integrated source SHA to the release workflow;
5. `release-readiness` independently confirms that SHA is still current protected `main`, requires terminal-success integrated `ci` and `SAST Semgrep`, resolves the merged PR that produced it, and requires that PR head's `ci`, `SAST Semgrep`, and `Security Scan` to be terminal-success;
6. the release workflow rebuilds the exact wheel/sdist evidence from that authorized SHA;
7. `publication-plan` compares every already-public PyPI filename/SHA-256 with the reviewed bundle and identifies only missing distributions before attestation/tag/GitHub Release side effects;
8. the isolated registry publisher receives only the selected credential and, when required, uploads only reviewed missing distributions;
9. post-publication verification proves the complete public artifact set corresponds byte-for-byte to the reviewed bundle and remains installable.

The development model must never approve, merge, tag, or publish its own output.

## Exact-head release checklist

Before irreversible release work:

- source SHA is the current protected `main` tip;
- integrated `ci` and `SAST Semgrep` are terminal-success;
- the exact merged PR producing that SHA is identified and its head `ci`, `SAST Semgrep`, and `Security Scan` are terminal-success;
- version metadata and `CHANGELOG.md` agree and `## Unreleased` contains no material omitted notes;
- Python support metadata agrees with the Python 3.10–3.14 matrix;
- production statement and branch coverage are exactly 100%;
- authored production public docstrings satisfy the repository contract;
- package build/install, dependency integrity, SAST/security, review, and workflow syntax gates pass;
- wheel and sdist are freshly built from the authorized SHA and hash-installed/smoke-tested outside source;
- any already-public files for the same version exactly match the rebuilt filename/SHA-256 evidence;
- SBOM/provenance/attestation succeeds;
- tag and GitHub Release identities match the authorized source SHA and package version.

## Automatic and recovery entry points

A raw protected-main `push` does **not** authorize release. Automatic release starts only from `workflow_run` completion of the repository `ci` workflow for `main`. The completed run's source SHA is revalidated against live protected `main` and the exact integrated/source-PR evidence above.

A stale completed-CI event is a successful no-op. If the reviewed version is already public, an ordinary automatic invocation is also a successful no-op before build. `workflow_dispatch` remains the explicit exact-current-main recovery/verification path and may rebuild an existing or partially published version after revalidating the same release-authority contract.

## Approved PyPI publisher modes

### GitHub-secret API token

The current approved production path uses the ContextualWisdomLab organization secret `PIPY_TOKEN`. Only the fully SHA-pinned `pypa/gh-action-pypi-publish` action in the isolated `publish-pypi` job may materialize `${{ secrets.PIPY_TOKEN }}` as its password input. The action's standard PyPI API-token username is `__token__`, so `PIPY_USERNAME` is deliberately not materialized.

Outside the publisher job, release readiness may observe only the **boolean availability fact** `secrets.PIPY_TOKEN != ''`. Token bytes must never appear in shell, logs, workflow outputs, cache keys, artifacts, SBOM/provenance, release notes, model jobs, build/test jobs, publication-planning jobs, or release receipts.

The selected API-token mode does not require an otherwise unconfigured `pypi` GitHub Environment merely to recreate the former OIDC prerequisite. Release safety is the accepted protected-main + exact release-authority contract above plus strict credential isolation.

### Trusted Publishing

Trusted Publishing remains an accepted future credential-minimization mode when its account-side OIDC relationship is configured. Migrating modes must be a reviewed change; the workflow must not silently fall back between API-token and OIDC after authentication/publication failure.

Using `PIPY_TOKEN` through the reviewed publisher is an approved path, not a bypass. Manual workstation uploads, ad-hoc credentials, weakened gates, rewritten tags, mutable action references, `skip-existing`, and credential disclosure remain prohibited.

## Partial-publication planning and recovery

HTTP 200 from the PyPI version endpoint is not proof that both reviewed distributions are present. After rebuilding the release bundle, `publication-plan` must:

- parse the reviewed `SHA256SUMS.txt`;
- fetch the current PyPI exact-version file set;
- reject duplicate/unexpected public filenames;
- reject any public digest that differs from the rebuilt reviewed digest;
- compute the exact missing reviewed filenames;
- fail before attestation/tag/GitHub Release if files are missing and the approved publisher is unavailable;
- create a separate immutable artifact containing only missing reviewed distributions.

A complete matching public set skips registry upload. A matching partial set may upload only those missing files. Already-public filenames are never resent, and `skip-existing` is not used to hide conflicts.

## Artifact identity

Record at minimum:

- protected source SHA and source PR head SHA;
- package version and annotated tag;
- wheel filename + SHA-256;
- sdist filename + SHA-256;
- SBOM/provenance/attestation identifiers;
- GitHub Release identifier;
- CI/security/review run identities;
- publisher mode name, never credential material;
- publication timestamp/public package location;
- post-publication clean-install smoke result.

Never infer artifact identity from a mutable branch name.

## Public-artifact verification

After any required registry upload, the workflow polls PyPI with a bounded propagation retry. Retry is permitted only while the endpoint is unavailable or exposes a **matching incomplete subset**. Unexpected filenames or immutable digest mismatches fail immediately. A non-converging public set fails closed.

Only when PyPI's complete wheel/sdist filename and SHA-256 set equals the reviewed `SHA256SUMS.txt` may the workflow create a clean environment, install `threadweave==<version>`, and reproduce representative `THREAD` and `UID THREAD` behavior. A successful upload alone is not release completion.

## Rollback and re-release

- Prefer a new patch release for corrected public artifacts; do not replace immutable files in place.
- A release-authority/readiness/build/publication-plan/attestation failure creates no new release publication side effect appropriate to its stage.
- Existing tags/releases are accepted only when their exact evidence matches the authorized source and reviewed bundle; never rewrite or clobber them.
- If PyPI authentication fails after immutable GitHub evidence exists, repair the approved publisher and manually retry the same exact protected-main release identity.
- If PyPI contains a correct subset, manual recovery may publish only missing reviewed files after revalidating existing hashes.
- If upload succeeds but public verification fails, preserve immutable artifacts, investigate, and retry verification; never republish the same filename/version.
- A runtime rollback normally selects the previous known-good package because ThreadWeave owns no persistence.

## Licensing

The repository uses Apache-2.0. Distribution must preserve `LICENSE` and any third-party notice obligations introduced later. The runtime currently has zero dependencies, minimizing runtime license exposure; build/test tools remain reviewed supply-chain inputs. Do not add an empty `NOTICE` solely to satisfy a checklist.

## Release notes

Release notes must disclose compatibility-significant fail-closed changes, including tighter identifier/graph/Unicode/ordering/serialization/publication-authority behavior.

## Completion rule

A release is complete only after the public artifact set is complete, its hashes/provenance correspond to the authorized protected head, a clean environment installs it, representative `THREAD`/`UID THREAD` smoke passes, and issue #17 is reconciled. After that, immediately continue the repository product loop.
