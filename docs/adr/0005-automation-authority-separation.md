# ADR-0005: Separate development, verification, publication, review, and release authority

**Status:** Accepted  
**Date:** 2026-08-09

## Context

Autonomous model-backed development is useful only if untrusted repository/model execution cannot acquire the credentials or authority needed to approve, merge, tag, or publish its own work. Repository-controlled tests are also untrusted relative to workflow secrets.

## Decision

Autonomous development uses distinct trust phases: model proposal, credential-free independent verification, trusted bounded PR publication, organization-central review/security/merge, and separately gated release. NVIDIA model credentials are held outside repository-controlled execution. GitHub/OIDC/reviewer/release credentials are not exposed to the development model or repository test process. The development loop never grants itself formal approval or protected-branch merge/release authority.

## Consequences

- A successful model run is not merge evidence.
- Exact-head verification and independent review remain separate gates.
- Credential boundary regressions require dedicated workflow-contract tests.
- Central `.github` policy can evolve without embedding privileged merge logic in runtime source.
- Any change that combines model execution with publication/review/release credentials requires a superseding ADR and threat-model review.