# ThreadWeave

ThreadWeave is a standards-grounded, runtime-dependency-free Python package for deterministic email conversation threading.

It combines the JWZ container model with RFC 5322 message identification, RFC 2047 header decoding, RFC 5256 base-subject extraction and THREAD serialization, RFC 5051 Unicode casemap comparison, and bounded sent-date ordering.

## Install

```bash
pip install threadweave
```

ThreadWeave supports Python 3.10 through 3.14 and ships a PEP 561 `py.typed` marker.

## What ThreadWeave owns

ThreadWeave owns in-process message threading and related standards behavior. It accepts normalized message identifiers, raw headers, or Python standard-library `email.message.Message` objects and produces deterministic conversation trees or RFC 5256 THREAD responses.

Hosts remain responsible for authentication, tenancy, mailbox persistence, search policy, network protocols, and deployment.

## Start with

- [Repository overview and examples](https://github.com/ContextualWisdomLab/ThreadWeave#readme)
- [Research and standards](research/README.md)
- [Supply-chain policy](supply-chain.md)
- [Product/technical gap baseline](product-technical-gap-baseline.md)
- [Hourly autonomous maintenance](operations/hourly-autonomous-maintenance.md)

## Quality posture

The repository requires complete owned production statement/branch coverage, production docstrings, multi-version Python CI, package build/install verification, dependency checks, and fail-closed handling for malformed historical mail, cycles, deep chains, and invalid mailbox identifiers.

Release and registry publication claims are valid only after the corresponding protected-main release workflow and public-artifact verification complete.
