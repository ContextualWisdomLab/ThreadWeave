# ADR-0008: Fail closed on Trusted Publishing identity before release side effects

**Status:** Accepted  
**Date:** 2026-08-10

## Context

ThreadWeave publishes immutable Python distributions from a manually dispatched protected-main workflow. PyPI publication uses GitHub OIDC through PyPI Trusted Publishing rather than a long-lived package token. The publishing job references a GitHub deployment environment named `pypi`.

Current GitHub deployment documentation requires the environment to be created before a workflow job uses it and applies required reviewers, self-review prevention, and branch/tag restrictions when the environment-referencing job is evaluated. In the previous ThreadWeave release job order, build/attestation, an annotated Git tag, and a GitHub Release could be created before the late `publish-pypi` job exposed a missing or incorrectly protected `pypi` environment or an account-side Trusted Publisher failure. That can leave externally visible release side effects even though the package was never published to PyPI.

The PyPI Trusted Publisher account relationship itself is intentionally external to repository source and cannot be truthfully manufactured by a workflow. Repository code can, however, fail before irreversible release work unless the GitHub half of the trust relationship is already present with the reviewed protection policy and the requested version is not already published.

## Decision

The release workflow SHALL begin with a credential-minimal `release-readiness` job that executes before build, attestation, tag creation, GitHub Release creation, or PyPI publication.

The readiness job SHALL:

1. run only for the canonical repository and protected `main` release invocation;
2. use only read permissions required to inspect repository Actions/environment configuration;
3. require the `pypi` GitHub environment to be **pre-created**, as required by GitHub's environment deployment model, rather than deferring the missing-environment failure to the late publishing job;
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

The readiness gate verifies configuration, not the eventual human deployment approval. The `publish-pypi` job continues to reference the `pypi` environment so GitHub applies its required-reviewer policy before that job receives the OIDC publication authority.

A failed OIDC/Trusted Publisher relationship MUST NOT be bypassed with a **long-lived PyPI token** or a **manual upload**. Repository automation must preserve the separately gated tag, GitHub Release, provenance/SBOM, and PyPI publication authority defined by ADR-0005.

## Consequences

- A missing `pypi` environment becomes a deterministic pre-release failure instead of a late publishing surprise.
- Required-reviewer configuration, self-review prevention, and protected-branch policy become machine-checked release prerequisites before irreversible release work.
- The actual environment approval remains enforced by GitHub on the environment-bound publishing job.
- A dispatch for an already published version fails before new tag/release side effects.
- The workflow still cannot prove the PyPI account-side Trusted Publisher configuration until OIDC publication is attempted; issue/release acceptance must keep that external evidence explicit.
- Repository maintainers must configure the environment and PyPI publisher before the first 0.2.0 release.
- Retry/recovery procedures must distinguish preflight failures (no release side effects) from later attestation/tag/release/publication failures.

## Rejected alternatives

### Defer environment existence/protection checks to the publishing job

Rejected because the publishing job runs after build/attestation/tag/GitHub Release stages in the current release topology, so preventable repository-side readiness failures would be discovered only after externally visible side effects.

### Store a PyPI API token as a GitHub secret

Rejected because it introduces a long-lived publish credential and bypasses the accepted OIDC identity boundary.

### Manually upload artifacts after a Trusted Publishing failure

Rejected because it breaks reproducible provenance and creates an artifact whose publication path does not match the reviewed release workflow.

### Create tag/GitHub Release first and treat every PyPI readiness failure as normal recovery

Rejected as the default path because the GitHub environment state and public version-existence state can be checked before those side effects. Later account-side or provider failures may still require idempotent recovery, but preventable readiness failures should occur first.

## Verification

Repository tests must prove the release workflow contains the readiness job before `build-release`, that `build-release` depends on it, that the job requires the reviewed environment protections, that its Harden Runner endpoint set is exact, and that public version existence is checked before any tag/release job can run.

Public release completion still requires issue #17 acceptance: exact protected-head CI/security/coverage/package evidence, successful environment approval and Trusted Publishing, SLSA/SPDX evidence, tag/GitHub Release identity, public PyPI wheel and sdist, and clean post-publication install/THREAD smoke.

## References — APA 7th

GitHub. (n.d.). *Deployments and environments*. GitHub Docs. Retrieved August 10, 2026, from https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments

GitHub. (n.d.). *Managing environments for deployment*. GitHub Docs. Retrieved August 10, 2026, from https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments

GitHub. (n.d.). *REST API endpoints for deployment environments*. GitHub Docs. Retrieved August 10, 2026, from https://docs.github.com/en/rest/deployments/environments

Python Packaging Authority. (n.d.). *Adding a Trusted Publisher to an existing PyPI project*. PyPI Docs. Retrieved August 10, 2026, from https://docs.pypi.org/trusted-publishers/adding-a-publisher/

Python Packaging Authority. (n.d.). *Security model and considerations*. PyPI Docs. Retrieved August 10, 2026, from https://docs.pypi.org/trusted-publishers/security-model/

Python Packaging Authority. (n.d.). *Publishing with a Trusted Publisher*. PyPI Docs. Retrieved August 10, 2026, from https://docs.pypi.org/trusted-publishers/using-a-publisher/