# ACTIVE_TASK — bounded task contract template

Template for one bounded task in the agent-loop discipline. Sections marked
REQUIRED are machine-checked by the source repository's lifecycle tooling;
inside a portable export they are structural recommendations. The one
always-portable rule is the acceptance boundary: after independent review,
only an explicit manual owner decision accepts, and no engineer, reviewer,
or auditor can accept. Skills constrain procedure and never expand scope.

## Release

`<project>-vMAJOR.MINOR.PATCH-codename` — one release id per task.

## Status

`ACTIVE` (or another canonical `TaskLifecycle` state; never a free-text one).

## Owner authorization

The verbatim owner direction and its exact scope, plus what is NOT
authorized (capital, credentials, production, publication, Git operations).

## Objective

One paragraph: what closes, reusing which already-accepted primitives. No
second orchestrator, no new dependency, no scope expansion.

## Owner-value alignment

REQUIRED. Money/evidence objective; why now; fastest valid route; owner-time
impact; material contextual assumptions exposed honestly.

## Delivery ROI gate

REQUIRED in the source repository for open work; source-internal and
optional outside it — it never becomes a portable default. When used:
value class; a named downstream value milestone; immediate points;
readiness delta; owner zero-point approval with the verbatim record for
zero-point work; writer and audit run caps; an explicit stop-loss. The
source-specific domain vocabulary (trading-PnL paths, ED-030 points) is
recorded in the source repository only.

## Required skills

REQUIRED. A `task_required_skills:` list. Every listed skill is read fully
before editing and applied; the implementation report carries one structured
evidence row per skill.

## Capital safety classification

REQUIRED. `REQUIRED` or `NOT_APPLICABLE`. Real-capital surfaces force the
privileged acceptance class; repository state alone never authorizes a live
action.

## Owner acceptance class

REQUIRED. After independent review, only an explicit manual owner decision
accepts a task; no engineer, reviewer, or auditor can accept, and the
portable reference has no standing-delegation or autonomous alternative. The
source-internal class vocabulary (autonomous standing delegation versus a
privileged owner gate) is recorded and marked in the source repository only,
outside this portable reference; it never becomes an alternative portable
default here.

## Engineer selection

Optional and source-internal: some source repositories pin an engineer
model per task. When used, record the routing policy, requested model and
variant, task complexity, selection reason, and escalation evidence.
Escalation requires reproduced material inability with concrete task-bound
evidence — never file count, elapsed time, token totals, or a first
failing run. The portable reference never selects a provider, and this
section never becomes a portable default.

## Intent preflight

REQUIRED in the source repository's machine-checked new-policy lifecycle;
inside a portable export it is a structural recommendation. One compact
section in the task itself — never a second spec store, generated document,
or dependency:

```text
## Intent preflight

- Mode: `LIGHT | FULL`
- Clarification status: `RESOLVED | NOT_NEEDED | BLOCKED`
- Open material clarification IDs: `NONE`
- Assumption IDs: `NONE | <comma-separated ids>`
- Requirement IDs: `<comma-separated unique ids>`

### Requirement coverage

| Requirement | Success criterion | Validation command | Planned evidence |
|---|---:|---:|---|
| R1 | 1 | 1 | `<non-empty planned evidence class>` |
```

Any open material clarification ID, a `BLOCKED` clarification status, or
materially ambiguous work facts are material ambiguity: they can never
start paid work. The required mode is derived deterministically from the
task's already-declared work facts plus the conservative candidate
footprint: LIGHT is available only to low-risk, routine, clear,
strong-oracle, contradiction-free, unrestricted work; an understated
declared mode fails closed, and declaring FULL stays allowed. FULL maps
every requirement to exactly one existing numbered success criterion and
one existing validation-command ordinal; missing, duplicate, orphaned,
malformed, and out-of-range references fail closed.

## Delivery topology

`SINGLE` (one exclusive candidate writer) or a read-only parallel topology.
The implementer never reviews, audits, or accepts its own candidate.

## Exact scope

The files to create or change; the unchanged hash-bound dependencies; the
explicit non-goals. Generated context and lifecycle state stay under the
existing lifecycle only.

## Candidate path allowlist

REQUIRED when a frozen candidate envelope is used. Exact forward-slash
repository-relative paths, one per line, inside a ```text fence. Every
final focused-runner capture must be complete over exactly these members.

## Validation seed

`0` unless the task declares another integer seed. The seed is applied
before the run and only the actually applied value is reported.

## Validation command budget

REQUIRED. The exact focused commands that may run, each with its declared
occurrence count and order. Everything else (full suites, broad runners,
live providers, network tests, production data, Git repair) is forbidden.
Results are reported from observed output; future steps are planned, never
preclaimed.

## Stop conditions

What stops the attempt honestly and returns it for adjudication: unexplained
drift, scope conflict, missing prerequisite acceptance, lifecycle or
validation failure. Gates are never weakened and success is never fabricated.

## Success criteria

Numbered, verifiable criteria that distinguish implemented, deterministically
tested, runtime verified, and finally accepted.

## Final independent audit

`REQUIRED` or a justified risk-gated skip. One immutable credential-free
package per candidate; acceptance never rests on a non-passing audit.
