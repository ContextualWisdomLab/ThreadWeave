# ADR-0005: Separate development, verification, publication, review, and release authority

**Status:** Accepted  
**Date:** 2026-08-09

## Context

Autonomous model-backed development is useful only if untrusted repository/model execution cannot acquire the credentials or authority needed to approve, merge, tag, or publish its own work. Repository-controlled tests are also untrusted relative to workflow secrets.

Official publication and workflow-identity records already treat credentials as
job-scoped, least-privilege material rather than a shared development secret:

- GitHub OpenID Connect issues a short-lived JWT unique to one workflow job.
  After a cloud or package registry validates the claims, it returns a token
  that exists only for that job and then expires (GitHub, n.d.-a).
- The workflow `GITHUB_TOKEN` is an automatic job identity. GitHub documents
  that workflows should grant it only the minimum permissions required, and that
  a separate GitHub App or stored token is required only when those built-in
  permissions are insufficient (GitHub, n.d.-b).
- PyPI Trusted Publishing exists specifically to replace long-lived API tokens.
  The security model requires trusting a named owner, repository, and isolated
  publishing workflow; it recommends job-level `id-token: write`, a dedicated
  environment, and never treating a successful workflow run as proof that the
  uploaded code is safe (Python Packaging Authority, n.d.-a, n.d.-b).

Those records do not authorize a development model to approve, merge, tag, or
publish its own output. Combining model execution with OIDC, reviewer, or
release credentials would collapse the identity boundary the catalogs describe.

## Decision

Autonomous development uses distinct trust phases: model proposal, credential-free independent verification, trusted bounded PR publication, organization-central review/security/merge, and separately gated release. NVIDIA model credentials are held outside repository-controlled execution. GitHub/OIDC/reviewer/release credentials are not exposed to the development model or repository test process. The development loop never grants itself formal approval or protected-branch merge/release authority.

## Consequences

- A successful model run is not merge evidence.
- Exact-head verification and independent review remain separate gates.
- Credential boundary regressions require dedicated workflow-contract tests.
- Central `.github` policy can evolve without embedding privileged merge logic in runtime source.
- Any change that combines model execution with publication/review/release credentials requires a superseding ADR and threat-model review.

## References

GitHub. (n.d.-a). *OpenID Connect*. GitHub Docs. Retrieved September 25, 2026,
from
https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/about-security-hardening-with-openid-connect

GitHub. (n.d.-b). *Use GITHUB_TOKEN for authentication in workflows*. GitHub
Docs. Retrieved September 25, 2026, from
https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication

Python Packaging Authority. (n.d.-a). *Publishing with a Trusted Publisher*.
PyPI Docs. Retrieved September 25, 2026, from
https://docs.pypi.org/trusted-publishers/using-a-publisher/

Python Packaging Authority. (n.d.-b). *Security model and considerations*. PyPI
Docs. Retrieved September 25, 2026, from
https://docs.pypi.org/trusted-publishers/security-model/
