# ADR-0002: Keep the threading core transport-neutral

**Status:** Accepted  
**Date:** 2026-08-09

## Context

Threading is useful to IMAP servers, migration tools, local archives, and CWL
services. If the core owns sockets, command parsing, authentication, mailbox
persistence, tenant state, or database access, it becomes difficult to reuse and
much harder to test deterministically.

The published standards already separate conversation structure from transport
session state. Zawinski (1997–2002) describes a container graph over message
identifiers. RFC 5256 §4 then defines `thread-data` as a presentation encoding
of that graph for IMAP `THREAD` responses (Crispin & Murchison, 2008). RFC 9051
is the current IMAP4rev2 base protocol: CRLF-terminated lines, `nz-number`
identifiers, and the rule that registered IMAP4rev1 extensions remain valid
unless an extension says otherwise (Melnikov & Leiba, 2021). Neither document
requires the threading implementation to own sockets, capability advertisement,
or mailbox persistence.

Header identity is likewise transport-neutral. RFC 5322 §3.6.4 defines the
identification fields (Resnick, 2008). RFC 2047 defines MIME encoded-words used
in those headers (Moore, 1996). RFC 6532 permits UTF-8 in most header values so
a host can carry internationalized text without ASCII coercion (Yang et al.,
2012). The runtime therefore normalizes identifiers and header text in process,
then lets a host or IMAP gateway project the resulting tree.

ThreadWeave is a leaf standard-library package. Naruon is a composition hub that
imports the published package; there is no sibling-checkout contract. PEP 561
requires a `py.typed` marker when a distribution ships inline type information
(Smith, 2017), which is how hosts consume the public typed API.

## Decision

The runtime package owns pure metadata normalization, thread construction, optional ordering, and pure protocol presentation only. `imap` may serialize `thread-data` and `* THREAD` values but owns no network/session state. Hosts own authentication, authorization, tenancy, mailbox storage/synchronization, distributed locking, rate limiting, audit, and external API lifecycle.

## Consequences

- The package remains zero-runtime-dependency and independently testable.
- Naruon or another host integrates through public typed values rather than database coupling.
- Mailbox sequence numbers and UIDs are caller-supplied protocol metadata, not ThreadWeave persistence keys.
- Adding a network/database capability to runtime requires a new ADR and security/operability redesign.

## References

Crispin, M., & Murchison, K. (2008). *Internet Message Access Protocol—SORT and
THREAD extensions* (RFC 5256). RFC Editor. https://doi.org/10.17487/RFC5256

Melnikov, A., & Leiba, B. (Eds.). (2021). *Internet Message Access Protocol
(IMAP)—Version 4rev2* (RFC 9051). RFC Editor.
https://doi.org/10.17487/RFC9051

Moore, K. (1996). *MIME (Multipurpose Internet Mail Extensions) Part Three:
Message Header Extensions for Non-ASCII Text* (RFC 2047). RFC Editor.
https://doi.org/10.17487/RFC2047

Resnick, P. (Ed.). (2008). *Internet Message Format* (RFC 5322). RFC Editor.
https://doi.org/10.17487/RFC5322

Smith, E. H. (2017). *Distributing and packaging type information* (PEP 561).
Python Enhancement Proposals. https://peps.python.org/pep-0561/

Yang, A., Steele, S., & Freed, N. (2012). *Internationalized Email Headers*
(RFC 6532). RFC Editor. https://doi.org/10.17487/RFC6532

Zawinski, J. (1997–2002). *Message threading*.
https://www.jwz.org/doc/threading.html
