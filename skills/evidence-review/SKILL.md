---
name: evidence-review
description: Independently review a frozen candidate or assess a completion claim using contract checks and material adversarial challenges; never grants implementation or acceptance authority.
---

# Evidence review

Use a session separate from the engineer when independent review is required. Receive the
task, skill closure, candidate and raw proof, not a target verdict. If only one session is
available, label the result self-review and preserve any unmet independent-review gate.

Recompute identity and verify checks against the frozen candidate. Look for drift after
the last GREEN. Pass one asks whether the task was met; pass two challenges a material
blind spot. For high risk use a reviewer-owned counterexample, oracle or boundary trace,
not just the engineer's test suite. A mock-only or prose-only PASS is insufficient.

Separate blocking reproduced defects from cosmetic debt. Give stable finding IDs,
reproduction and consequence; batch related fixes. FULL tasks need complete requirement
coverage with no remaining material IDs. No acceptance from missing or contradictory proof.

Do not modify the reviewed candidate. Reviewer evidence may be written only in an
authorized isolated realm. A repaired candidate needs new identity-bound review. Acceptance
belongs to the configured owner boundary; review success alone is not release approval.
