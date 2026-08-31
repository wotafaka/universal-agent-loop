# Portable workflow

## Pick a topology, not a brand

| Mode | Context arrangement | Honest guarantee |
|---|---|---|
| Single tool, separate sessions | Architect, engineer and reviewer use fresh bounded contexts in one available tool | Role/context separation; model errors can still correlate |
| Multiple tools/providers | Same roles, explicit local model bindings | Diversity may help; does not prove independent evidence |
| One chat only | One assistant implements and runs checks | Self-check only; independent review remains unavailable |

One model can fill different roles in separate sessions. A renamed persona inside
one running conversation is not a fresh session. Do not pass full engineer history
to the reviewer; supply task, candidate, constraints and raw evidence, not a desired verdict.

## Authority and evidence are different

Owner instructions and project rules say what is permitted. Raw evidence says what
happened. Neither replaces the other. An installed tool is not authorization; an
allowed command is not proof it ran. Skills never grant new authority.

Architect: define scope, risk, checks, role bindings and repair decisions.
Engineer: sole candidate writer; tests and implementation report, never acceptance.
Reviewer: read-only candidate inspection plus authorized isolated checks and its own
evidence output. Cannot repair the candidate it is currently judging.
Observer: optional read-only process evidence assistant, never reviewer or approver.
Owner: accepts or explicitly configures a bounded standing delegation.

Manual acceptance is portable default. Do not inherit the source owner's private
standing delegation. Sensitive access, deployment, publication, irreversible deletion
or financial operations need their specific permission even in an autonomous loop.

## One task is the contract

Use [the task template](../templates/TASK.md), not parallel spec/plan/task databases.
For a routine, clear, LOW-risk task with strong checks and no restricted authority or
contradiction, use LIGHT. Otherwise FULL adds explicit assumptions, stable requirement
IDs and requirement → success criterion → validation → evidence coverage.
Unknown risk is not low risk. Check the actual candidate paths, not only the author's
labels: governance, authentication, acceptance and destructive/data paths can raise risk.
Never shrink those labels merely to get a cheap route past a gate.

Resolve only material questions before implementation; safe reversible details can
remain explicit assumptions. An unanswered question affecting scope, correctness,
safety or acceptance blocks a paid writer. No mandatory long-form specification.

## Implement, capture, freeze, review

1. Architect authorizes one bounded task, its validation budget and required skills.
2. Engineer receives only needed context. Reproduce the missing behavior before code
   changes when TDD applies; preserve genuine RED and subsequent GREEN.
3. Record commands, working directory, environment policy, exit/output and candidate
   identity. A test result belongs to the bytes actually tested.
4. Finalize candidate, run final checks, then finalize the report. Explicitly exclude
   only the report from test-time digests if the runtime supports this two-layer policy;
   the report still belongs to the final acceptance envelope.
5. Freeze task, skill closure, candidate members and validation artifacts with exact
   bytes/SHA-256. Reviewer recomputes decisive evidence, not just reads engineer prose.
6. Review two questions: does it meet the contract; can the contract/tests miss a
   material defect? HIGH-risk changes require a reviewer-owned negative case, independent
   oracle or boundary trace. Two passes need not mean two paid model calls.
7. FULL review covers the exact frozen requirement IDs; unresolved material requirements
   cannot be accepted. Any relevant candidate/task/skill/proof drift invalidates review.
8. Owner decision binds the reviewed candidate. Update current state and record lessons.

Task states are not evidence states: implemented, tested, reviewed, accepted and released
mean different things. Missing output stays UNKNOWN; failed checks stay failed. Local
hashes detect accidental drift, not a hostile same-account process able to rewrite both
files and hashes. A trusted verifier/manifest must come from outside the suspect payload.

## Autonomy without blind retries

Continue material same-scope repairs while there is demonstrable progress. No default
attempt, elapsed-time or token-total cap ends a progressing task. Explicit user spending
limits and real platform limits still apply; do not purchase quota or change route silently.

A new iteration needs changed candidate evidence, new raw evidence, a falsified
hypothesis with its outcome, or a demonstrated route failure and justified new action.
Changing timestamps, filenames, titles or iteration numbers is not progress. With the
same substantive state, investigate a new falsifiable cause or report the missing input;
do not launch an identical paid run. A valid negative audit is not a provider outage.

Stop for new authority, unresolved material ambiguity, unsafe conditions or an actual
external blocker. Bundle related confirmed findings into one repair. Cosmetic debt does
not force another implementation/audit round. Record it without blocking delivery.
