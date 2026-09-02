---
name: karpathy-guidelines
description: Engineering discipline for design, implementation, refactor and review; explicit assumptions, smallest verifiable outcome, surgical changes and goal-driven checks.
license: MIT
---

# Karpathy guidelines

Conceptual origin: publicly shared engineering principles by Andrej Karpathy,
re-authored here as an original concise adaptation under MIT. This is not a copy
of any external manual; load it when the trigger applies.

## Assumptions first

Before nontrivial work, write the material assumptions in one or two lines each.
An assumption you cannot state is a question you must ask. Resolve only what
blocks correctness, safety or acceptance; the rest stays an explicit assumption.

## Smallest verifiable outcome

Define the smallest user-visible result that proves the direction is right, and
the check that proves it. Build that first; widen only after it holds. A large
diff without a check is not progress you can trust.

## Surgical changes

Touch only what the outcome requires. No drive-by refactors, no style churn, no
speculative abstraction. If a change pulls unrelated edits with it, investigate
the shared boundary instead of widening the diff. Defer cosmetic debt explicitly.

## Goal-driven checks

Every change ends in a check someone could rerun: exact command, expected
result, observed result. Stronger oracles beat longer arguments. When a check
cannot exist, say so and bound the risk instead of claiming confidence.

## Review stance

Review against the stated outcome and the smallest sufficient check. Separate
reproduced blocking defects from taste; require evidence for both, but never
let taste block delivery or let missing evidence pass.
