---
name: invariant-testing
description: Test actual round-trip, idempotence, determinism, state-preservation or independent-oracle properties; do not force property tests onto ordinary example behavior.
---

# Invariant testing

Choose a property independently of the implementation: encode/decode round-trip,
idempotent replay, equivalent reference oracle, or a permitted state transition preserving
identity and safety. A test that recomputes the same algorithm is not independent.

Start with explanatory boundary cases. Use an already approved property library or a
bounded fixed-seed standard-library generator; installing a new dependency is not implied.
Keep the seed and smallest failing input. Test malformed, empty, repeated or Unicode
cases only where they cross the real boundary.

Generated cases use isolated bounded storage. Never loosen hash identity, origin, temporal
provenance or acceptance rules to pass. Record the property, counterexample, seed and
observed outcome. If no useful independent property exists, use examples and say so.
