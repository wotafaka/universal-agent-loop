# Bound review guard — scope and use

`validation/review_guard.py` is a separately versioned adapter over the preserved
reference core. It repairs ambiguous review declarations without rewriting historical
`reference/` bytes. Run its focused regressions from the package root:

```text
python -I -S -B -m unittest discover -s tests -v
python -I -S -B reference/smoke.py
```

The first command tests the new seam. The second only tests the historical example;
its PASS alone does not cover the repair. Both use synthetic evidence, not real owner
decisions or independent provider proofs. Actual delivery checks: [VALIDATION](VALIDATION.md).

## Public boundary

In a Python integration where the package root is an explicit import location:

```python
from validation.review_guard import validate_bound_review

refusals = validate_bound_review(
    review_text,
    root=evidence_root,
    task_id=expected_task_id,
)
if refusals:
    # Report and stop this review gate; do not proceed to acceptance.
    raise ValueError(refusals)
# Only this bound review/correction gate passed. Other gates remain mandatory.
```

`root` must be the real evidence directory, not `None`; `task_id` must be the expected
task identity. Both are mandatory keyword arguments. These are not authorization
tokens. Proof records still must exist and match the task and artifact identities.
The optional `reference_root` supports an explicit location for the same pinned
snapshot, not a substitute arbitrary core.

Before importing reused code the adapter verifies the pinned reference manifest and
every listed member's bytes/hash. Legitimate snapshot replacement needs an explicit
new pin and verification; do not auto-refresh the pin from whatever files are present.
This detects local drift under LOCAL_INTEGRITY assumptions, not hostile same-account
tampering with both verifier and package or a separate OS security boundary.

## Human report versus machine report

`templates/REVIEW.md` is a human-facing template. Its table is **not** the historical
machine grammar. A runtime integration must explicitly generate/check the machine
representation and preserve reviewer authority and evidence; feeding the human table
to the validator must not silently mean “no findings”.

The bound guard's canonical format requires these four exact top-level headings once:

```text
## Contract compliance
## Adversarial validity
## Findings
## Durable correction
```

Each pass section requires one canonical verdict declaration, `- Verdict: ` followed
by backticked `PASS` or `FAIL`, plus the historical bound evidence declarations.
Duplicate, conflicting or noncanonical declarations are refusals, not “first one wins”.
The four required heading strings may appear only as those standalone headings, never
again in narrative or historical headings. This deliberate strictness prevents the
legacy first-substring parser from selecting a different section than the guard.
Use only empty lines, one `- NONE`, or canonical `- M1: nonempty finding text` lines
inside Findings. IDs follow `[A-Z]{1,8}[0-9]+`; no table, free prose, alternative list
marker, indented finding, duplicate ID or mixing NONE with findings. Put narrative
elsewhere. Every material ID needs the historical evidence-bearing durable correction.

Do not fabricate proof JSON to make a report parse. The executable synthetic examples
in `tests/test_review_guard.py` show syntax and negative cases only, not real review
evidence. For an actual task the integration must produce and independently verify the
corresponding artifacts and candidate bindings.

## What this adapter does NOT do

An empty refusal list is not owner acceptance, a successful full delivery, or permission
to start a model. It does not implement writer claims, launchers, lifecycle bookkeeping,
automatic role selection, privilege checks, FULL-task convergence, the high-risk
reviewer-owned challenge, required external audit or final candidate revalidation.
The synthetic composition test demonstrates only the gates it actually calls.

A runtime must compose every required gate and fail closed if any is absent or fails.
Manual owner acceptance remains the public default. Do not call the raw historical
review parser alone as an alternative accepting route: its preserved permissive behavior
is why this adapter exists. See [RUNTIME](RUNTIME.md) and [STATUS](STATUS.md).
