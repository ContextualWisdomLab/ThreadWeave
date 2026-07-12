# AGENTS.md — threadweave

Operating guide for automated agents working on this repository.

`threadweave` is a faithful implementation of the JWZ message-threading
algorithm (https://www.jwz.org/doc/threading.html). Its value is *correctness* —
mail clients rely on threading being right and never hanging. Treat every change
to `threading.py` and `container.py` as behaviour-sensitive.

## Invariants that must not regress

1. **Loop-safety.** No input may cause an infinite loop or crash. Self-links and
   mutual reference cycles must terminate. `Container.has_descendant`,
   `add_child`, and `iter_descendants` all guard with a visited set — do not
   remove those guards. Before linking A as a parent of B, check that A is not
   already a descendant of B.
2. **Never reparent a container that already has a good parent.** In step 1.B,
   only link a referenced container that is still parentless. A message's own
   `References` (step 1.C) is the sole authority allowed to override a
   *presumed* parent, and only when the new link would not create a loop.
3. **Empty-container pruning correctness (step 4).** Nuke empty childless
   containers; splice-promote the children of an empty container into its level.
   At the **root level**, an empty container with more than one child is kept as
   a grouping root; an empty root with exactly one child promotes that child.
   Do not "simplify" this special case away.
4. **Missing roots become placeholders.** A referenced-but-unseen `Message-ID`
   yields an empty container that still co-threads its descendants.
5. **Duplicate Message-IDs must not collide destructively.** A second distinct
   message with an already-seen ID gets its own container; both survive.
6. **Determinism.** Output order derives from first appearance in the input.
   `id_table` relies on dict insertion order — keep it.

## Maintenance notes

- Pure standard library only (`re`, `hashlib`, `dataclasses`, `typing`). Do not
  add runtime dependencies.
- The header primitives in `headers.py` are extracted behaviour-preserving from
  naruon; port fixes in both directions and keep their behaviour identical.
- TDD: add or update a test (thread count / co-threading membership are the most
  robust assertions) before changing the algorithm.

## Verify

```bash
pip install -e ".[test]" ruff
ruff check .
pytest -q
```
