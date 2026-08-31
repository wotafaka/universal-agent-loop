# Architect Review — <task id>

Independent review artifact. One review per candidate. The reviewer never
writes the implementation and never accepts on the implementer's behalf;
reviewer prose alone is not evidence.

## Decision

The verdict that follows the evidence: an accepting verdict or a concrete
repair requirement with the reproduced material defect.

## Evidence boundary

What the reviewer independently recomputed or re-executed, and what remains
implementer-reported (and therefore unverified).

## Delivery efficiency disposition

Optional outside the source repository (source-internal measurement loop).
When used: exactly one terminal decision per triggered recommendation id:

- `<RECOMMENDATION_ID>`: `APPLY_NEXT_TASK` or `NO_ACTION_WITH_REASON` — reason

## Contract compliance

- Verdict: `PASS`
- Evidence: `validation-review-proof/1` artifact `<repo-relative path>` sha256 `<sha256 of the exact stored bytes>` origin `REVIEWER_RECOMPUTED` action `<what was recomputed>` candidate `<task id>`

## Adversarial validity

- Verdict: `PASS`
- Evidence: `validation-review-proof/1` artifact `<repo-relative path>` sha256 `<sha256>` origin `REVIEWER_REEXECUTED` action `<what was re-executed>` candidate `<task id>`

Both passes are mandatory for an accepting verdict. Each evidence line must
bind one existing artifact whose exact stored bytes hash to the recorded
digest; only reviewer-owned origins (`REVIEWER_RECOMPUTED`,
`REVIEWER_REEXECUTED`) count; a failing pass underneath an accepting verdict
fails closed.

## Findings

- M1: one material finding, citing raw evidence and the reviewer's own
  recomputation or re-execution step. Cosmetic or theoretical items are
  recorded as non-blocking debt, never as invented findings.

## Convergence disposition

Required in the source repository for a FULL-task accepting review;
source-internal and optional outside it. An accepting review is
evidence-bound to the frozen task requirement IDs:

- Disposition: `CONVERGED | MATERIAL_DELTA`
- Covered requirement IDs: `<exact frozen requirement id set>`
- Remaining material requirement IDs: `NONE | <exact remaining ids>`

A material-delta verdict names the exact remaining requirement IDs and can
never be accepted; unknown, overlapping, duplicated, or inconsistent
requirement ids fail closed. LIGHT-task reviews carry no extra convergence
burden.

## Durable correction

Exactly one terminal outcome per material finding:

- Mandated change: `NONE`
- M1: `NONE_REQUIRED` — rationale: why no durable change is warranted — evidence: `<path>#<anchor resolving inside the stored file bytes>`

`LESSON_RECORDED` must bind the lessons file; `RULE_PROMOTED` must bind
both a rule anchor and a verifying test; `NONE_REQUIRED` combined with a
mandated change for the same finding is a contradiction. A review is never
acceptance: acceptance is the separate explicit manual owner decision,
bound to this exact reviewed candidate, that follows it.
