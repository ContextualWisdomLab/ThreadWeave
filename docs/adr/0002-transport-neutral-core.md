# ADR-0002: Keep the threading core transport-neutral

**Status:** Accepted  
**Date:** 2026-08-09

## Context

Threading is useful to IMAP servers, migration tools, local archives, and CWL services. If the core owns sockets, command parsing, authentication, mailbox persistence, tenant state, or database access, it becomes difficult to reuse and much harder to test deterministically.

## Decision

The runtime package owns pure metadata normalization, thread construction, optional ordering, and pure protocol presentation only. `imap` may serialize `thread-data` and `* THREAD` values but owns no network/session state. Hosts own authentication, authorization, tenancy, mailbox storage/synchronization, distributed locking, rate limiting, audit, and external API lifecycle.

## Consequences

- The package remains zero-runtime-dependency and independently testable.
- Naruon or another host integrates through public typed values rather than database coupling.
- Mailbox sequence numbers and UIDs are caller-supplied protocol metadata, not ThreadWeave persistence keys.
- Adding a network/database capability to runtime requires a new ADR and security/operability redesign.