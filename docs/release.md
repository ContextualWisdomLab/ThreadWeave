# Release operations

ThreadWeave releases are built once from an exact reviewed protected `main` commit, transferred between jobs as one immutable Actions artifact, attested, tagged, published to GitHub, uploaded to PyPI through an explicitly approved publisher, and then verified from the public index. Runtime dependencies remain empty; release tooling is installed only from the reviewed hash lock.

## Publisher configuration

The currently approved PyPI publisher uses the ContextualWisdomLab organization GitHub Secret named exactly `PIPY_TOKEN`. The value is never read, displayed, copied, or persisted by repository code. GitHub injects it only into the isolated `publish-pypi` job as the `password` input of the fully SHA-pinned `pypa/gh-action-pypi-publish` action. That action uses the normal PyPI API-token username `__token__`, so the existing `PIPY_USERNAME` organization secret is intentionally not materialized.

PyPI Trusted Publishing remains an accepted future publisher mode. If the repository later adopts it, the isolated publishing job may use `id-token: write` with the corresponding PyPI account-side Trusted Publisher identity and omit the password input. Do not silently fall back between API-token and OIDC modes after a failed publication attempt.

Treat publisher workflow changes as production credential-boundary changes. Neither publisher mode relaxes exact-head CI, independent review, digest, provenance, tag, or public-verification requirements.

## Changelog-driven release contract

The reviewed package version is the canonical three-component final version such as `0.2.0`. The workflow can start from either:

- a protected `main` push that changes release authority (`CHANGELOG.md`, package version metadata, the release contract, or the release workflow); or
- a manual `workflow_dispatch` recovery invocation whose optional version must equal the reviewed package version.

The workflow fails closed unless all of the following agree:

- `[project].version` in `pyproject.toml`;
- `threadweave.__version__`;
- one dated `CHANGELOG.md` release section with a valid calendar date;
- an empty material `## Unreleased` section for a final release;
- exactly one regular, non-linked wheel and one regular, non-linked source distribution whose filenames contain that version.

Before new release work, the readiness job queries PyPI. If the exact reviewed version is already public, an ordinary protected-main trigger is a no-op rather than an attempted overwrite. If the version is not public, the approved publisher must be available before build/tag/GitHub Release side effects begin.

The release section must contain material notes and no `TODO`, `TBD`, or `Unreleased` placeholder. Public versions follow PEP 440; the narrower three-component release rule preserves Semantic Versioning and makes tags, artifacts, PyPI records, and support documentation unambiguous. Symbolic links, hard links, stale output directories, mismatched versions, and duplicate artifacts are rejected rather than normalized or overwritten.

## Job separation

The workflow uses seven distinct authority boundaries:

1. **Release readiness** — read-only exact-head checkout; confirm protected `main`, derive the reviewed version, compare any manual recovery version, check public-version existence, and reduce publisher-secret availability to a boolean without materializing token bytes.
2. **Build** — read-only checkout; install `requirements/ci.lock` with `--require-hashes`; regenerate and compare the lock; run Ruff, compileall, doctests, full statement and branch coverage, package checks, and an installed-wheel smoke test; create wheel, sdist, `SHA256SUMS.txt`, release notes, and an SPDX 2.3 JSON SBOM.
3. **Attest** — download the exact build artifact; verify its checksum manifest; generate signed SLSA build provenance and an SBOM attestation with GitHub's OIDC-backed `actions/attest`. This is the only API-token-mode job that needs `id-token: write`.
4. **Tag** — create an annotated `v<version>` tag only after build and attestation. A retry accepts an existing tag only when it is annotated and peels to the same reviewed commit.
5. **GitHub Release** — publish the exact distributions, checksum manifest, SPDX document, and release notes against the verified tag. A matching existing release is accepted only when its notes, complete asset-name set, checksum manifest, SPDX document, and downloaded distribution digests are identical. The workflow never edits or clobbers existing release evidence.
6. **PyPI publish** — download the same artifact, verify `SHA256SUMS.txt` immediately before upload, and invoke the pinned PyPA publisher with only `PIPY_TOKEN`. PyPA-side attestations are disabled in this credential mode because GitHub SLSA/SBOM attestations are already generated separately and the publisher does not receive OIDC authority.
7. **Public verification** — download the reviewed bundle without any publisher secret, compare PyPI's wheel/sdist filename and SHA-256 set with `SHA256SUMS.txt`, create a clean virtual environment, install the exact public version, and reproduce representative `THREAD` and `UID THREAD` behavior.

No build or test command runs in jobs that hold tag, release, attestation, or PyPI publishing authority. Every runner blocks undeclared network egress and each external action is pinned to a complete commit SHA.

## SPDX version and checksum policy

SPDX 3.0.1 is the current approved SPDX specification. ThreadWeave deliberately emits SPDX 2.3 JSON for this release path because GitHub's current SBOM attestation and verification contract uses the predicate URI `https://spdx.dev/Document/v2.3`. This is an interoperability choice, not a claim that SPDX 2.3 is the newest model. Migration to SPDX 3.x should occur only when the attestation producer, GitHub verifier, downstream consumer tooling, and stored predicate contract can move together.

The SPDX 2.3 file model requires a SHA-1 checksum, and a package with `filesAnalyzed: true` requires the SPDX package verification code derived from sorted file SHA-1 values. ThreadWeave therefore emits SHA-1 solely for SPDX 2.x compatibility and computes it with Python's `usedforsecurity=False` flag. It also emits SHA-256 for every file; `SHA256SUMS.txt` and GitHub artifact attestations remain the release-integrity and authenticity evidence. A consumer must not treat the compatibility SHA-1 value as the release security boundary.

The SPDX document includes `documentDescribes`, package-to-file relationships, `hasFiles`, a PyPI package URL, Apache-2.0 declarations, a package verification code, and both SHA-1 and SHA-256 file checksums. Its namespace includes a digest of the reviewed artifact manifest and contains no URI fragment.

## SPDX and provenance evidence

`scripts/ci/release_contract.py` emits deterministic release notes, a sorted SHA-256 checksum manifest, and the SPDX 2.3 document. The creation time is the release date at `00:00:00Z`, not the runner clock, so the evidence can be reproduced from reviewed source and artifacts.

GitHub's attestation service signs SLSA provenance and the SPDX statement with a short-lived Sigstore identity derived from the attestation job's workflow OIDC token. PyPI publication authorization is a separate boundary: currently the approved organization API token, optionally Trusted Publishing in a future reviewed migration.

Verify downloaded GitHub artifacts with:

```bash
gh attestation verify threadweave-0.2.0-py3-none-any.whl \
  --repo ContextualWisdomLab/ThreadWeave

gh attestation verify threadweave-0.2.0-py3-none-any.whl \
  --repo ContextualWisdomLab/ThreadWeave \
  --predicate-type https://spdx.dev/Document/v2.3
```

For PyPI files, compare the public project JSON filename/SHA-256 set to the reviewed `SHA256SUMS.txt`; the release workflow performs this check before clean-install smoke.

## Procedure

1. Integrate the release candidate through normal protected-main policy after current-head CI, SAST, Security Scan, coverage, package checks, and independent review succeed.
2. Confirm `CHANGELOG.md`, `pyproject.toml`, and `threadweave.__version__` contain the same intended version and that material `Unreleased` notes are empty.
3. Confirm the approved organization publisher secret is available to ThreadWeave. Do not expose or copy its value.
4. Merge the release-authority change to protected `main`; the changelog-driven workflow starts automatically when its watched release files changed. Use **Release ThreadWeave** manual dispatch only for an idempotent recovery attempt.
5. Review each job's exact commit, artifact digest, annotated tag, GitHub Release, GitHub attestations, PyPI filename/digest set, and clean-install smoke result.
6. Close the release blocker only after the public artifact verification succeeds.

## Failure and rollback

- A readiness, validation, or build failure creates no new tag and publishes nothing.
- An attestation failure creates no new tag and publishes nothing.
- If a matching tag already exists, the workflow accepts it only when it is an annotated tag that resolves to the current reviewed commit.
- A GitHub Release retry is read-only. Any changed note, missing or extra asset, modified checksum manifest, modified SPDX document, or distribution digest mismatch is a hard failure.
- If PyPI authentication fails after the tag/GitHub Release exists, repair the approved publisher authority and retry the same exact protected release head; tag/release verification is idempotent and must not rewrite evidence.
- PyPI versions and files are immutable. Do not replace a broken file. Yank the affected release when appropriate, document the reason, fix the source through a new PR, and publish a new patch version.
- Never bypass a failed hash, provenance, version, release-immutability, or publisher-authority check with a manual workstation upload, an ad-hoc credential, or weakened branch/review/security policy.

## References (APA 7th edition)

GitHub. (n.d.). *Secrets*. GitHub Docs. https://docs.github.com/en/actions/concepts/security/secrets

GitHub. (n.d.). *Using artifact attestations to establish provenance for builds*. https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations

Python Packaging Authority. (n.d.). *Publishing with a Trusted Publisher*. https://docs.pypi.org/trusted-publishers/using-a-publisher/

Python Packaging Authority. (n.d.). *gh-action-pypi-publish*. https://github.com/pypa/gh-action-pypi-publish

Python Software Foundation. (2013). *Version identification and dependency specification* (PEP 440). https://peps.python.org/pep-0440/

Python Software Foundation. (2024). *Index support for digital attestations* (PEP 740). https://peps.python.org/pep-0740/

SPDX Workgroup. (2022). *SPDX specification 2.3*. https://spdx.github.io/spdx-spec/v2.3/

SPDX Workgroup. (2025). *SPDX specification 3.0.1*. https://spdx.github.io/spdx-spec/v3.0.1/

Supply-chain Levels for Software Artifacts. (2025). *SLSA specification, Version 1.2*. https://slsa.dev/spec/v1.2/
