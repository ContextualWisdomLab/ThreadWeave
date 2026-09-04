# ADR-0008: Fail closed on release publisher identity before release side effects

**Status:** Accepted  
**Date:** 2026-08-10  
**Amended:** 2026-09-01

## Context

ThreadWeave publishes immutable Python distributions from an exact protected-main release workflow. The original decision required PyPI Trusted Publishing through a GitHub `pypi` environment and treated the absence of that external OIDC relationship as the sole release blocker.

That assumption no longer matches the accepted organization credential boundary. ContextualWisdomLab already maintains an approved organization GitHub Actions secret named exactly `PIPY_TOKEN`, and `fast-mlsirm` has an established reviewed pattern that passes that token only to a pinned PyPA publisher action. GitHub organization secrets are explicitly designed to make one centrally managed secret available to selected repositories; a workflow receives a secret only when it explicitly references it. PyPI and the PyPA publishing action continue to support API-token authentication as well as Trusted Publishing.

The architectural requirement is therefore not “OIDC only.” The requirement is that one approved publisher identity be selected before irreversible release work, that its credential surface be isolated from build/test/release evidence, that release authority be tied to the exact reviewed integration and required checks, and that the public artifact be verified after publication.

A second release-authority problem is concurrency. GitHub Flow permits `main` to continue after an integrated release candidate has been accepted. A tag is an immutable name for the authorized commit; it is not a lock on the branch. Trying to require `main` to remain unchanged until the later tag push creates an unavoidable time-of-check/time-of-use window because the branch read and the tag-ref creation are different remote operations. Git's `--atomic` option makes the refs included in one push transactional, while `--force-with-lease=<ref>:<expect>` only protects a ref that is itself being updated. A no-op push of `main` is not a portable cross-ref compare-and-swap primitive for tag creation. Therefore release authority must have one explicit linearization point rather than pretending a later branch read can atomically guard the tag.

## Decision

The release workflow SHALL begin only after the repository's ordinary `ci` workflow has completed successfully for `main`, or through an explicit manual recovery invocation on the exact current protected-main head. A raw `push` SHALL NOT directly authorize publication.

All release workflow runs for the repository SHALL use one repository-scoped concurrency group with `cancel-in-progress: false`. The complete workflow run, not only the publisher job, is serialized across candidate SHAs.

The credential-minimal `release-readiness` job is the **release-authority linearization point**. It SHALL execute before build, attestation, tag creation, GitHub Release creation, or PyPI publication and SHALL:

1. bind one immutable source SHA from the completed `ci` run or the explicit manual protected-main recovery invocation;
2. verify at this linearization point that the source SHA is the exact current protected `main` tip; stale automatic completions are successful no-ops and a stale manual recovery fails closed;
3. require terminal-success `ci` and `SAST Semgrep` push runs for that integrated source SHA;
4. resolve the merged pull request that produced the source SHA and require its exact head to have terminal-success `ci`, `SAST Semgrep`, and `Security Scan` pull-request runs;
5. derive one canonical `MAJOR.MINOR.PATCH` version from reviewed package metadata and require any manual recovery version to equal it;
6. query the public PyPI project API without treating HTTP 200 as proof of a complete release;
7. make an automatic invocation a successful no-op when that reviewed version is already public, while preserving `workflow_dispatch` as the explicit exact-main recovery/verification path;
8. prove only the **availability** of the selected publisher credential without materializing its value into shell, logs, outputs, artifacts, caches, SBOM/provenance, or release receipts;
9. fail closed on missing required release authority, malformed metadata, unavailable publisher for missing files, or unexpected GitHub/PyPI responses.

Once a serialized run passes this complete readiness boundary, that exact SHA is the immutable release source for the selected version. A later `main` commit does **not** retroactively supersede the already-authorized release candidate; it is later GitHub-Flow work. If later work must replace an already-authorized candidate before publication, it must establish a different release identity/version rather than silently stealing the same immutable version. This makes the readiness decision the auditable serialization point and avoids claiming a cross-ref atomicity guarantee that GitHub tag creation does not provide.

After the exact wheel and sdist are rebuilt, a separate credential-free publication-planning job SHALL compare every already-public PyPI filename and SHA-256 against the reviewed `SHA256SUMS.txt` **before** attestation/tag/GitHub Release side effects. Unexpected files or digest mismatches fail immediately. A complete matching public set requires no registry upload. A matching partial set may recover only by publishing the reviewed missing distributions; already-public filenames are not resent and `skip-existing` is not used.

### Approved publisher mode: organization PyPI API token

The current release path uses the organization secret `PIPY_TOKEN`. Only the isolated `publish-pypi` job may pass `${{ secrets.PIPY_TOKEN }}` to the fully SHA-pinned `pypa/gh-action-pypi-publish` action as its `password` input. The action's PyPI API-token username default (`__token__`) is sufficient, so the existing organization `PIPY_USERNAME` secret is deliberately not materialized.

The release-readiness, build, publication-planning, attestation, tag, GitHub Release, and public-verification jobs MUST NOT receive the token value. Readiness may evaluate `secrets.PIPY_TOKEN != ''` to one boolean availability fact, but the value itself must never cross the publisher boundary.

The API-token publisher does not require an otherwise unconfigured `pypi` GitHub Environment merely to recreate the former OIDC prerequisite. Deployment safety is provided by protected-main integration plus the exact release-authority checks above and by isolating the credential to the final pinned publisher action. A future repository policy may add an environment as a separately accepted deployment-control decision, but doing so is not implicit in API-token authentication.

### Optional publisher mode: PyPI Trusted Publishing

Trusted Publishing remains an accepted and preferred credential-minimization option once the account-side OIDC relationship is configured. A future migration may give the isolated publisher `id-token: write` and remove the password input. It must be a reviewed publisher-mode change; the workflow must not silently fall back between API-token and OIDC modes after an authentication or publication failure.

### Automatic release entry point

The automatic release entry point is `workflow_run` completion of the repository `ci` workflow for `main`, not a raw push. The completed run supplies the candidate source SHA. Because release runs are repository-serialized, readiness independently verifies that SHA against live protected `main` and the required exact integrated/source-PR evidence before the run is authorized. That successful readiness decision is the release candidate's linearization point.

If the reviewed version is already public, ordinary automatic invocations stop successfully before build. `workflow_dispatch` remains an idempotent recovery/verification entry point for the exact current protected-main release identity, including a matching partial publication. Both paths converge on one release contract and do not create separate release engines.

## Security invariants

Using `PIPY_TOKEN` through the reviewed publisher is an approved authentication path, not a bypass. The following remain prohibited:

- printing, echoing, serializing, fingerprinting into evidence, or otherwise exposing the token;
- passing the token to readiness, build, test, model, publication-planning, attestation, tag, GitHub Release, or public-verification jobs;
- publishing before exact integrated and source-PR release authority reaches terminal success;
- manual workstation uploads used to escape a failed automated control;
- unreviewed publisher code or mutable third-party action references;
- `skip-existing`, release-tag rewrite, artifact replacement, self-approval, fabricated checks, or weakened branch/security/review gates;
- silently switching credential modes after an authentication failure.

The publisher receives only reviewed missing distributions whose SHA-256 values were generated by the exact authorized build. Post-publication verification MUST compare PyPI's complete published filename/digest set with those reviewed hashes and perform a clean install plus representative protocol smoke before release completion.

Public verification may retry bounded registry propagation only when PyPI is absent or exposes a matching incomplete subset. Unexpected filenames or immutable digest mismatches fail immediately and are never retried into acceptance.

## Consequences

- The external absence of a PyPI Trusted Publisher no longer blocks ThreadWeave while the approved `PIPY_TOKEN` is available.
- Credential exposure is narrower than a generic username/password workflow because only `PIPY_TOKEN` is needed and only the publisher job materializes it.
- OIDC can be adopted later without changing package/release semantics.
- A missing token for required missing distributions fails before attestation/tag/GitHub Release side effects.
- Raw protected-main pushes cannot race publication against required checks; automatic release begins from completed main CI and revalidates the complete accepted evidence boundary.
- Repository-scoped workflow concurrency gives one release candidate at a time. The exact readiness decision is the linearization point, so later GitHub-Flow commits cannot rewrite the already-authorized version/source pairing.
- A version already present on PyPI becomes a successful no-op for ordinary automatic release invocations, preserving public-version immutability and avoiding repeated tag failures.
- Manual recovery can rebuild and verify an existing/partial publication without resending already-public files.
- Public-artifact digest and clean-install evidence become part of release completion rather than an out-of-band manual step.
- Issue #17 remains the acceptance record for the first public `0.2.0` release, now tracking approved publisher execution rather than external OIDC setup.

## Rejected alternatives

### Keep Trusted Publishing as the only accepted publisher

Rejected because it would preserve an artificial external blocker even though an organization-approved PyPI API token already exists and can be isolated to the exact publisher job.

### Pass both `PIPY_USERNAME` and `PIPY_TOKEN`

Rejected for the current PyPA API-token path because the publisher supports the `__token__` username convention. Materializing an unnecessary second secret violates credential minimization.

### Put the token in a workflow-level environment variable

Rejected because every job would inherit publication authority. The token belongs only to the pinned publisher action input in the isolated registry job.

### Trigger publication directly on protected-main push

Rejected because required integrated/review evidence can still be running after the push event. Starting from completed main CI and independently rechecking the exact evidence prevents irreversible release work from outrunning required gates.

### Re-read `main` immediately before tag creation and treat it as an atomic guard

Rejected because the branch read and the tag-ref creation are separate remote operations. `main` can move between them. Git's documented atomic push guarantees apply only to refs in the same remote transaction, and an exact-value lease protects the ref being updated; ThreadWeave will not directly update protected `main` merely to manufacture a tag CAS. The serialized readiness snapshot is the release-authority boundary instead.

### Treat any existing PyPI version as complete

Rejected because PyPI can expose one distribution while another upload failed or is still propagating. Existing public files must be compared to the rebuilt reviewed bundle, and only matching missing files may be recovered.

### Manually upload after workflow failure

Rejected because it breaks reproducible provenance and creates an artifact whose publication path does not match the reviewed release workflow.

### Silently fall back between OIDC and token modes

Rejected because authentication ambiguity after side effects makes incident reconstruction and release authority unverifiable. Publisher mode must be explicit and deterministic for one release attempt.

## Verification

Repository tests must prove that:

- the automatic trigger is completed main `ci`, not raw `push`, and manual recovery remains explicit;
- all release runs share one repository-scoped, non-cancelling concurrency group;
- readiness binds one source SHA, rejects/stops stale authority appropriately, is the single release-authority linearization point, and precedes all release work;
- tag creation uses the exact already-authorized source SHA and does not claim a later non-atomic `main` read as a CAS guarantee;
- exact integrated `ci`/`SAST Semgrep` plus associated merged-PR head `ci`/`SAST Semgrep`/`Security Scan` must be terminal-success before release work;
- automatic already-public versions are successful no-ops while manual exact-main recovery may rebuild/verify an existing or partial publication;
- readiness sees only token availability, not token bytes;
- the token value appears exactly once in workflow source, as the pinned publisher action password input;
- `PIPY_USERNAME` is not materialized;
- only the attestation job holds `id-token: write` while API-token publication is selected;
- Harden Runner endpoint sets remain exact per job;
- an existing public artifact set is compared to the rebuilt reviewed bundle before immutable release side effects, and only matching missing files are selected for upload;
- public verification retries only bounded absence/matching-incomplete propagation and fails immediately on unexpected files or digest mismatch;
- post-publication complete PyPI filename/SHA-256 equality and clean-install protocol smoke are required.

Public release completion still requires issue #17 acceptance: exact protected-head CI/security/coverage/package evidence, SLSA/SPDX evidence, immutable tag/GitHub Release identity, public PyPI wheel and sdist, digest equality, and clean post-publication install/THREAD smoke.

## References — APA 7th

Git. (n.d.). *git-push documentation*. Git. Retrieved September 1, 2026, from https://git-scm.com/docs/git-push

GitHub. (n.d.). *Secrets*. GitHub Docs. Retrieved September 1, 2026, from https://docs.github.com/en/actions/concepts/security/secrets

GitHub. (n.d.). *Secrets reference*. GitHub Docs. Retrieved September 1, 2026, from https://docs.github.com/en/actions/reference/security/secrets

GitHub. (n.d.). *Deployments and environments*. GitHub Docs. Retrieved September 1, 2026, from https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments

Python Packaging Authority. (n.d.). *Publishing with a Trusted Publisher*. PyPI Docs. Retrieved September 1, 2026, from https://docs.pypi.org/trusted-publishers/using-a-publisher/

Python Packaging Authority. (n.d.). *gh-action-pypi-publish*. GitHub. Retrieved September 1, 2026, from https://github.com/pypa/gh-action-pypi-publish
