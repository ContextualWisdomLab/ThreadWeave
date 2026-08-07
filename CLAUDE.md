# Claude / Coding-Agent Instructions

Read and follow [`AGENTS.md`](AGENTS.md) as the canonical repository policy. Do not
create a second, conflicting rule set here.

For every change:

1. Preserve the batch threader as the correctness oracle.
2. Work test-first and retain 100% production statement and branch coverage.
3. Add beginner-readable docstrings to every authored production callable.
4. Keep runtime dependencies at zero unless an approved architecture decision says
   otherwise.
5. Update `CHANGELOG.md`, user documentation, and standards references when public
   behavior changes.
6. Never bypass current-head CI, security scans, independent review, release
   identity checks, or the release-blocker contract.
7. GitHub product-development automation uses the isolated NVIDIA NIM/OpenCode
   boundary. Do not introduce `COPILOT_GITHUB_TOKEN` or alter existing review-agent
   credentials.
