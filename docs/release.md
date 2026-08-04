# Release operations

ThreadWeave releases are built once from reviewed `main`, transferred between
jobs as one immutable Actions artifact, attested, tagged, published to GitHub,
and finally uploaded to PyPI through Trusted Publishing. Runtime dependencies
remain empty; release tooling is installed only from the reviewed hash lock.

## External configuration

Repository code cannot create or approve the PyPI trust relationship. Before the
first production upload, configure a PyPI Trusted Publisher with exactly these
claims:

| Field | Value |
|---|---|
| Owner | `ContextualWisdomLab` |
| Repository | `ThreadWeave` |
| Workflow | `release.yml` |
| Environment | `pypi` |

Create a GitHub environment named `pypi`. Configure required reviewers and limit
deployment to the protected default branch. The publish job alone receives
`id-token: write`; it has no long-lived PyPI password or API token. Treat changes
to this workflow and environment as changes to a production credential boundary.

PyPI accepts a pending publisher for a project that has not yet been created, so
the same identity can establish the first release. Confirm that the package name
is available and that the publisher claims are exact before dispatching.

## Release contract

A release input is a canonical three-component final version such as `0.2.0`.
The workflow fails closed unless all of the following agree:

- the requested version;
- `[project].version` in `pyproject.toml`;
- `threadweave.__version__`;
- one dated `CHANGELOG.md` release section with a valid calendar date;
- exactly one regular, non-linked wheel and one regular, non-linked source
  distribution whose filenames contain that version.

The release section must contain material notes and no `TODO`, `TBD`, or
`Unreleased` placeholder. Public versions follow PEP 440; the narrower
three-component release rule preserves Semantic Versioning and makes tags,
artifacts, PyPI records, and support documentation unambiguous. Symbolic links,
hard links, stale output directories, mismatched versions, and duplicate
artifacts are rejected rather than normalized or overwritten.

## Job separation

The top-level workflow is intentionally non-reusable because the PyPI Trusted
Publisher identity includes the workflow filename and environment. It uses five
distinct jobs:

1. **Build** — read-only checkout; install `requirements/ci.lock` with
   `--require-hashes`; regenerate and compare the lock; run Ruff, compileall,
   doctests, full statement and branch coverage, package checks, and an installed
   wheel smoke test; create wheel, sdist, `SHA256SUMS.txt`, release notes, and an
   SPDX 2.3 JSON SBOM.
2. **Attest** — download the exact build artifact; verify its checksum manifest;
   generate signed SLSA build provenance and an SBOM attestation with GitHub's
   OIDC-backed `actions/attest`.
3. **Tag** — create an annotated `v<version>` tag only after build and attestation.
   A retry accepts an existing tag only when it is annotated and peels to the
   same reviewed commit.
4. **GitHub Release** — publish the exact distributions, checksum manifest, SPDX
   document, and release notes against the verified tag. A matching existing
   release is accepted only when its notes, complete asset-name set, checksum
   manifest, SPDX document, and downloaded distribution digests are identical.
   The workflow never edits or clobbers existing release evidence.
5. **PyPI publish** — download the same artifact into an isolated `pypi`
   environment, verify `SHA256SUMS.txt` immediately before upload, and invoke the
   official PyPA publisher with Trusted Publishing. PEP 740 publish attestations
   are enabled; duplicate versions fail instead of being silently skipped.

No build or test command runs in the jobs that hold tag, release, attestation, or
PyPI publishing authority. Every runner blocks undeclared network egress and each
external action is pinned to a complete commit SHA.

## SPDX version and checksum policy

SPDX 3.0.1 is the current approved SPDX specification. ThreadWeave deliberately
emits SPDX 2.3 JSON for this release path because GitHub's current SBOM
attestation and verification contract uses the predicate URI
`https://spdx.dev/Document/v2.3`. This is an interoperability choice, not a claim
that SPDX 2.3 is the newest model. Migration to SPDX 3.x should occur only when
the attestation producer, GitHub verifier, downstream buyer tooling, and stored
predicate contract can move together.

The SPDX 2.3 file model requires a SHA-1 checksum, and a package with
`filesAnalyzed: true` requires the SPDX package verification code derived from
sorted file SHA-1 values. ThreadWeave therefore emits SHA-1 solely for SPDX 2.x
compatibility and computes it with Python's `usedforsecurity=False` flag. It also
emits SHA-256 for every file; `SHA256SUMS.txt`, GitHub artifact attestations, and
PyPI attestations remain the release-integrity and authenticity evidence. A
consumer must not treat the compatibility SHA-1 value as the release security
boundary.

The SPDX document includes `documentDescribes`, package-to-file relationships,
`hasFiles`, a PyPI package URL, Apache-2.0 declarations, a package verification
code, and both SHA-1 and SHA-256 file checksums. Its namespace includes a digest
of the reviewed artifact manifest and contains no URI fragment.

## SPDX and provenance evidence

`scripts/ci/release_contract.py` emits deterministic release notes, a sorted
SHA-256 checksum manifest, and the SPDX 2.3 document. The creation time is the
release date at `00:00:00Z`, not the runner clock, so the evidence can be
reproduced from reviewed source and artifacts.

GitHub's attestation service signs SLSA provenance and the SPDX statement with a
short-lived Sigstore identity derived from the workflow OIDC token. PyPI's PEP
740 implementation separately binds each uploaded distribution to the Trusted
Publisher identity and digest. These are complementary: GitHub records how the
artifact was built, while PyPI records which trusted workflow published the
specific index file.

Verify downloaded GitHub artifacts with:

```bash
gh attestation verify threadweave-0.2.0-py3-none-any.whl \
  --repo ContextualWisdomLab/ThreadWeave

gh attestation verify threadweave-0.2.0-py3-none-any.whl \
  --repo ContextualWisdomLab/ThreadWeave \
  --predicate-type https://spdx.dev/Document/v2.3
```

For PyPI files, inspect the project's Integrity API provenance record and verify
that its publisher references `ContextualWisdomLab/ThreadWeave`, `release.yml`,
and the `pypi` environment.

## Procedure

1. Confirm the PR queue is empty and current `main` CI, SAST, and Security Scan
   are successful.
2. Confirm `CHANGELOG.md`, `pyproject.toml`, and `threadweave.__version__` contain
   the intended version.
3. Confirm the `pypi` GitHub environment and PyPI Trusted Publisher claims.
4. Dispatch **Release ThreadWeave** from the default branch and enter the exact
   version without a leading `v`.
5. Review each job's exact commit, artifact digest, annotated tag, GitHub Release,
   PyPI provenance, and GitHub attestations.
6. Install the published wheel in a clean environment and repeat the documented
   THREAD/UID THREAD smoke example.

## Failure and rollback

- A validation or build failure creates no tag and publishes nothing.
- An attestation failure creates no tag and publishes nothing.
- If a matching tag already exists, the workflow accepts it only when it is an
  annotated tag that resolves to the current reviewed commit.
- A GitHub Release retry is read-only. Any changed note, missing or extra asset,
  modified checksum manifest, modified SPDX document, or distribution digest
  mismatch is a hard failure.
- PyPI versions and files are immutable. Do not replace a broken file. Yank the
  affected release, document the reason, fix the source through a new PR, and
  publish a new patch version.
- Never bypass a failed hash, provenance, environment, version, or release-
  immutability check with a manually uploaded package or long-lived API token.

## References (APA 7th edition)

GitHub. (n.d.). *Using artifact attestations to establish provenance for builds*.
https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations

Python Packaging Authority. (n.d.). *Integrity API*.
https://docs.pypi.org/api/integrity/

Python Packaging Authority. (n.d.). *Publishing with a Trusted Publisher*.
https://docs.pypi.org/trusted-publishers/using-a-publisher/

Python Packaging Authority. (n.d.). *Producing attestations*.
https://docs.pypi.org/attestations/producing-attestations/

Python Software Foundation. (2013). *Version identification and dependency
specification* (PEP 440). https://peps.python.org/pep-0440/

Python Software Foundation. (2024). *Index support for digital attestations*
(PEP 740). https://peps.python.org/pep-0740/

SPDX Workgroup. (2022). *SPDX specification 2.3*.
https://spdx.github.io/spdx-spec/v2.3/

SPDX Workgroup. (2025). *SPDX specification 3.0.1*.
https://spdx.github.io/spdx-spec/v3.0.1/

Supply-chain Levels for Software Artifacts. (2025). *SLSA specification,
Version 1.2*. https://slsa.dev/spec/v1.2/
