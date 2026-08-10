# ADR-0008: Fail closed on Trusted Publishing identity before release side effects

**Status:** Accepted  
**Date:** 2026-08-10

## Context

ThreadWeave publishes immutable Python distributions from a manually dispatched protected-main workflow. PyPI publication uses GitHub OIDC through PyPI Trusted Publishing rather than a long-lived package token. The publishing job references a GitHub deployment environment named `pypi`.

GitHub can create a referenced deployment environment when it does not already exist. An implicitly created environment has no reviewed protection rules. In the previous release job order, build/attestation, an annotated Git tag, and a GitHub Release could be created before the PyPI publishing job exposed a missing or incorrectly configured deployment environment or Trusted Publisher relationship. That can leave externally visible release side effects even though the package was never published to PyPI.

The PyPI Trusted Publisher account relationship itself is intentionally external to repository source and cannot be truthfully manufactured by a workflow. Repository code can, however, fail before irreversible release work unless the GitHub half of the trust relationship is already configured and the requested version is not already published.

## Decision

The release workflow SHALL begin with a credential-minimal `release-readiness` job that executes before build, attestation, tag creation, GitHub Release creation, or PyPI publication.

The readiness job SHALL:

1. run only for the canonical repository and protected `main` release invocation;
2. use only read permissions required to inspect repository Actions/environment configuration;
3. require the `pypi` GitHub environment to be **pre-created** rather than allowing the publishing job to create an unprotected environment implicitly;
4. require at least one environment reviewer and require the environment to **prevent self-review**;
5. require the environment deployment policy to allow only **protected branches**;
6. reject malformed release versions before using them in external lookups;
7. query the public PyPI project API and fail before release side effects if the requested version already exists;
8. fail closed on missing environment state, unexpected GitHub/PyPI responses, or unproven protection properties.

The actual PyPI Trusted Publisher claims remain externally configured and must match:

- owner: `ContextualWisdomLab`;
- repository: `ThreadWeave`;
- workflow: `release.yml`;
- environment: `pypi`.

A failed OIDC/Trusted Publisher relationship MUST NOT be bypassed with a **long-lived PyPI token** or a **manual upload**. Repository automation must preserve the separately gated tag, GitHub Release, provenance/SBOM, and PyPI publication authority defined by ADR-0005.

## Consequences

- A missing `pypi` environment becomes a deterministic pre-release failure instead of a late publishing surprise.
- Environment approval and protected-branch policy become machine-enforced release prerequisites.
- A dispatch for an already published version fails before new tag/release side effects.
- The workflow still cannot prove the PyPI account-side Trusted Publisher configuration until OIDC publication is attempted; issue/release acceptance must keep that external evidence explicit.
- Repository maintainers must configure the environment and PyPI publisher before the first 0.2.0 release.
- Retry/recovery procedures must distinguish preflight failures (no release side effects) from later attestation/tag/release/publication failures.

## Rejected alternatives

### Allow the publishing job to create the environment implicitly

Rejected because an implicitly created environment may lack required reviewers and protected-branch restrictions.

### Store a PyPI API token as a GitHub secret

Rejected because it introduces a long-lived publish credential and bypasses the accepted OIDC identity boundary.

### Manually upload artifacts after a Trusted Publishing failure

Rejected because it breaks reproducible provenance and creates an artifact whose publication path does not match the reviewed release workflow.

### Create tag/GitHub Release first and treat failed PyPI publication as normal recovery

Rejected as the default path because the account-side environment state can be checked before those side effects. Later failures may still require idempotent recovery, but preventable readiness failures should occur first.

## Verification

Repository tests must prove the release workflow contains the readiness job before `build-release`, that `build-release` depends on it, that the job requires the reviewed environment protections, that its Harden Runner endpoint set is exact, and that public version existence is checked before any tag/release job can run.

Public release completion still requires issue #17 acceptance: exact protected-head CI/security/coverage/package evidence, successful Trusted Publishing, SLSA/SPDX evidence, tag/GitHub Release identity, public PyPI wheel and sdist, and clean post-publication install/THREAD smoke.