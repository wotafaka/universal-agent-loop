---
name: data-footprint-safety
description: Bound and verify durable writes, journals, replay, retention, cleanup and migration without evidence loss or concurrent mutation.
---

# Data footprint safety

Before writes, identify active processes and the exact contained target. Inventory paths,
counts and bytes; classify raw immutable evidence, derived output and bounded audit records.
Declare expected growth, stable row identity, consumers and disk budget. Use isolated test data.

One writer per target. Atomic replacement for rebuildable current state; append-only only
for actual history. Never append a whole derived snapshot every run. Propagate nonzero
exits through wrappers. Unexpected growth or partial output is not success.

Production deletion, truncation, compression or migration needs explicit scope, verified
source/target manifests and a recovery plan. Resolve targets before acting; do not follow
an escaping link or delete a broad computed root.

Replay requires a bounded range, conflict policy, dry-run and isolated staging. Rerun the
same frozen input: no new semantic rows; any bounded audit growth must be explained.
Reconcile before/after manifests before promotion. Preserve distinct source observations;
space savings never justify merging different evidence.
