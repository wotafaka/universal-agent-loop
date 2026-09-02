# Runtime adapter contract

These are the enforced contracts of the runtime shipped in `agent_loop/`
(stdlib-only, CLI `python -m agent_loop --project <root> ...`). Every
enforced claim below is bound to an implementing module and focused
regressions under `tests/`; the mapping for all transfer IDs lives in
[TRANSFER](TRANSFER.md). All guarantees are LOCAL_INTEGRITY, not an OS
sandbox. Bind each claim to its implementing function and negative test
before marking it active in a fork.

## Task schema and CLI

One compact versioned task file is the only authoritative task database for the
executable path: `ual-task/1` JSON at `<project>/task.json`. A valid minimal FULL
example (a valid LIGHT task keeps `mode`, the fact fields, empty `requirements`,
and `success_criteria_count: 0`):

```json
{
  "schema": "ual-task/1",
  "id": "demo-task",
  "title": "Synthetic demo task",
  "mode": "FULL",
  "risk": "MEDIUM",
  "work_kind": "IMPLEMENTATION",
  "oracle_strength": "STRONG",
  "novelty": "ROUTINE",
  "ambiguity": "CLEAR",
  "failure_evidence": "NONE",
  "escalation_evidence": "NONE",
  "authority_domains": [],
  "material_contradiction": false,
  "clarification_status": "RESOLVED",
  "open_clarification_ids": [],
  "owner_actor": "OWNER",
  "requirement_ids": ["R1"],
  "success_criteria_count": 1,
  "requirements": [
    {"id": "R1", "criterion": 1, "command": 1, "evidence": "TEST_OUTPUT"}
  ],
  "validation": {
    "commands": [
      {"ordinal": 1, "cwd": ".", "argv": ["python", "check.py"],
       "expected_outcomes": ["RED", "GREEN"]}
    ],
    "seed": "0",
    "environment": {"base": ["SYSTEMROOT", "PATH"], "overlay": {}}
  },
  "candidate": {"allowlist": ["src/demo.py"], "report": "report/IMPLEMENTATION.md"},
  "required_skills": [],
  "review": {"passes": 2},
  "audit": {"required": false},
  "observer": {"policy": "AUTO"},
  "generated_state": [],
  "lessons_path": ".agent-loop/lessons.md"
}
```

Command surface (all commands require `--project <root>` and print one JSON
line; exit 0 on success, 2 with stable refusal codes otherwise):
`task-validate`, `route check`, `status set`, `claim acquire|scan|bind-child|
release|abandon`, `run`, `validate record|status`, `event record`, `refresh`,
`report-check`, `close`, `envelope freeze|verify`, `review validate|seal`,
`accept`, `observer policy|record`, `audit package|verify|record|status`,
`pack build|verify`, `progress check`, `continuation prepare|verify`,
`context build|verify`, `report efficiency|delivery`.

Trusted local configuration lives in `<project>/.agent-loop/config.json`
(`ual-config/1`: `owner_actor`, neutral `role_bindings`, `audit_policy`);
untrusted task, candidate and evidence bytes are bound by digests in the
artifacts themselves.

## Provider boundary

Configure role → provider/model/effort locally, outside the universal policy. Probe
availability through permitted tools before launch. Record requested and observed
model identities separately; absent provider proof means observed=UNKNOWN.
Host approval/denial is binding. No hidden fallback, auth-file copying, weaker sandbox
or unrestricted environment inheritance to get a failing route working.
Transmit only the task's explicitly permitted, credential-free package. Owner consent
for one project does not automatically authorize transmission from another project.

## Single writer and process ownership

- Claim the actual shared write realm before spawning. A task-level lock alone is
  insufficient if two tasks can edit one checkout. Either serialize the checkout or
  use isolated worktrees with separate claims and review the eventual merged candidate.
- Atomic exclusive claim binds task/run, host, launcher PID and OS birth identity,
  child identity and exact candidate scope. PID alone is reusable, not proof of identity.
- Second writer refusal occurs before a second child exists. Do not test this on a live
  writer: use isolated fake-process fixtures for adapter acceptance.
- Retain the host tool's process/session identifier and poll that same run after a
  disconnect. A truncated response or missing UI output is not proof the child exited.
- Child output goes directly to durable task-local files; UI tailing is not the primary
  log. Bound storage and report overflow; never silently truncate evidence into a PASS.
- A terminal record binds actual exit, process identity, output bytes/digests and final
  observer receipt. FINISHED with a nonzero exit is terminal, not successful delivery.
- Release only on a verified terminal outcome. Ambiguous/crashed claims remain active
  until the authorized owner adjudicates the exact run. No automatic stale-lock deletion.
- Startup failures must leave honest provenance. A Windows invalid inherited stdin handle
  is a spawn-boundary defect, not grounds to cherry-pick a passing retry in another console.
- External file transmission (`run --stdin-file` / `--basis-file`) resolves through the
  containment primitive only: absolute paths, `..`, symlink/junction components and
  non-regular files refuse before any claim, run or child exists. Reads happen once under
  documented hard byte caps (stdin 8 MiB, basis 1 MiB), and the cap holds on the bytes
  actually read — one open reads at most cap+1 bytes, so a growth race between the size
  check and the read can never return more than the cap — before the claim is acquired.
  ENGINEER stdin must additionally be an immutable task-authorized pack — this task's
  digest-verified context pack or a manifest-bound repair pack for the attempt's bound
  iteration — and must pass the conservative secret scan before any claim/run/child.
  At that launch boundary a context-pack stdin must also pass the full read-only
  closure/hash/re-render verification (a synchronized suffix with an updated outer
  hash, or any live-member drift, refuses; no timing state is recorded there), and a
  repair-pack stdin must bind the current attempt's exact `progress.pack_iteration`,
  carry a write-once verification receipt still binding the current pack+manifest
  bytes, and pass the full read-only pack re-render. Ordinary non-engineer uses stay
  provider-neutral and contained.

## Mechanical supervision first; optional AI observer

Track PID/birth identity, exit, heartbeat/checkpoints, stalls and storage bounds without
an LLM. Choose observer policy from risk and oracle strength:

| Mode | Suggested trigger |
|---|---|
| NONE | Clear, routine, low-risk task with strong automated oracle |
| DEFERRED | Medium-risk, understood task; promote after a configured meaningful delay or anomaly |
| IMMEDIATE | High risk, novel behavior, weak oracle, authority-sensitive changes or reproduced material failure |

The original configuration uses 120 seconds for deferred promotion; that is a local
setting, not a universal timeout or a reason to kill an engineer. Real stalls need
observable lack of progress and a task-bound recovery decision.

The parent supplies task/run identity, allowed evidence paths, positions, safety scope,
complete observer instructions and an actual bounded initial evidence span. If the
observer cannot read files, relay raw spans inline and then only new deltas. Paths alone
are not delivered evidence. Reuse the same observer within the run; no full-history fork.
It must not run project startup/refresh/check, tests, providers or lifecycle mutations.

Record exactly one run-bound terminal receipt with the real route or honest unavailable
reason. ATTACHED proves route/allowlist, not that the model consumed bytes or proved a
served-model identity. Freeze the profile bytes and recheck drift. Do not repeat a
path-only probe that failed unchanged. Never rewrite historical receipts after a later
successful smoke. At terminalization resnapshot the receipt even if no heartbeat ran.
Observer summaries cannot authorize repair, clear a claim or replace independent review.

## Exact validation and lifecycle

Declare the exact commands, cwd, environment policy, allowed count/order and expected
phase outcomes before a fenced run. TDD RED and GREEN repeat the SAME reproduction
command; two differently spelled suites are not a RED/GREEN pair. Unlisted commands
do not become validation evidence just because they passed.

Capture executable/argv/cwd, candidate digest, complete stdout/stderr identity, exit,
and bounded before/after write inventory. A missing exit or unknown truncation state
is not complete proof. Same complete execution fingerprint with contradictory outcomes
is nondeterminism to investigate, not a majority vote; missing inputs are NOT_COMPARABLE.
Fingerprint includes candidate, command, environment, platform, seed and fixture/input.

If importing an exact-count legacy fence, do not improvise extra occurrences inside
the same run. An unexpected final RED returns to the architect for a new justified
iteration. It does not create an overall retry limit. Author the fence before paying
for a writer; boilerplate startup is permitted separately, not counted as a test.

Finish in the runtime's declared order: final GREEN → finalize report → generated-state
refresh → report check → engineer close. The portable CLI enforces exactly this order
(`agent_loop close` refuses otherwise) and rejects every further tool, run or validation
event after a successful close. If a fork's close is terminal, no tools after successful
close, including todo tools or a second close. A refused close does not arm that
terminal boundary.

## Evidence realms and acceptance

Separate candidate writes, generated state, raw evidence, reviewer evidence and owner
decisions. Bound canonical relative paths and resolve symlinks/junctions before reads
or writes. Unknown member classification fails closed; don't silently skip members.
Prefer explicit write-once artifacts and bounded atomic replacement for current state.

Freeze the task, actual skills and command budget, candidate paths/bytes/SHA-256,
validation artifacts, reviewer proofs, and acceptance actor. Recompute at review and
again at acceptance. Status-only normalization must have a declared versioned schema;
otherwise exact stored bytes are canonical. Never normalize away semantic changes.
Without Git, list explicit files and disclose unverified diff completeness.

## Audit and recovery

**Audit and recovery.** When a primary auditor is configured, every audit
result and quota receipt must carry a bound `ual-audit-route-receipt/1`:
task ID, exact audit package manifest/payload digests, requested model,
observed model, terminal `FINISHED` status, integer exit code, and the exact
result/raw-error file path, bytes and SHA-256. A primary PASS requires
exit 0 and `requested_model == model_observed == configured primary`. A valid
negative primary verdict remains a real result (never fallback) and still
needs the fully bound primary receipt. The quota receipt is no longer minted
from a bare reason string: `audit quota-receipt` requires a primary
`PROVIDER_FAILURE` route receipt bound to the same task/package whose
structured raw provider-error evidence (HTTP/API status 429 or an explicit
provider quota code, with terminal error) mechanically classifies as
`PRIMARY_QUOTA_EXHAUSTED`; `--reason` is only a cross-check. Fallback results
must identify the configured fallback and still require the same-package
quota receipt. Route receipts are tamper-evident local bindings under
LOCAL_INTEGRITY, not OS authentication.

The status/code/terminal facts are parsed from the bound UTF-8 JSON raw-error
bytes. Optional CLI fields only cross-check those bytes and cannot manufacture
quota evidence. Before admitting a fallback, the runtime revalidates the quota
receipt, referenced route receipt and raw-error bytes as one chain.
At final acceptance it also re-derives the current audit policy and revalidates
the audit package, result, route and quota chain. Temporarily removing `primary`,
recording an UNKNOWN audit and restoring the original config bytes cannot launder
that record through the configured-primary gate.

Send a secret-scanned immutable package bound to the exact latest candidate and task.
Verify bytes before use, and again on return. Bind verdict to package and actual route.
A successful provider process or outer AUDIT_RESULT is not an inner PASS.
Package verification re-renders the exact payload from the manifest-bound live inputs
and requires byte equality: exact task and directory iteration, canonical path ordering,
only the three declared input roles (`input`, `instruction`, `validation`), unique
complete declared input set, per-input live byte counts and hashes, declared totals,
exact framing and no trailing or unlisted bytes — synchronized payload+manifest
tampering refuses. When the task itself requires the audit, the package must carry the
exact candidate closure derived from the canonical live task plus the current frozen
envelope — the task contract, every frozen candidate member (allowlist plus report),
every required skill, and the decisive frozen validation evidence paths — with
identical identity, roles and order at build, verify, record and acceptance. Missing,
extra, duplicate, reordered or relabelled closure members refuse; when the caller
declares no inputs at all the builder auto-derives the whole closure, so caller
authority over the package contents is removed rather than duplicated and a task-only
subset can never pass while the outer hashes still look valid. Repair
packs and context packs verify the same way: the verifier re-derives the expected member
set from the live task contract, re-renders the pack from manifest/index-bound live
inputs and compares bytes, so a self-consistent outer hash without the exact embedded
inputs is never sufficient.
No old audit may accept a repaired candidate. Multiple conflicting terminal records
require adjudication rather than selecting the convenient result.

When the task requires audit and trusted config names a primary auditor, `audit record`
requires a validated route receipt whose requested and observed identities agree and
match the result's `requested_model`. Missing identity is a hard refusal, not an
acceptable `UNKNOWN`.
Fallback identity must name the configured fallback and still needs the exact-package
primary-quota receipt described below.

Fallback needs explicit policy and objective provider failure. A negative valid audit
is not a fallback trigger. The example's independent Sol fallback always stays visibly
different from Opus and requires manual owner acceptance. A local package-integrity
failure is BLOCKED, not a reason to transmit to another model.

A continuation package is allowed only for a proven terminal writer and no active
claim; bind prior log/sidecar hashes, task, launch identity and last checkpoint.
Missing or drifted identity cannot be repaired by prose. Repair-pack sequencing is in
[CONTEXT](CONTEXT.md). Preserve old artifacts; new iterations do not rewrite history.

## Port acceptance tests

Required gate composition of the accepting runtime: validate task/preflight syntax AND
separately reject
material ambiguity before spawn; derive actual footprint and allowed route; bind the
candidate/skill/command closure; validate execution evidence; perform bound review and
durable correction; require FULL convergence and the high-risk challenge when applicable;
validate any required latest-candidate audit; finally verify the manual owner decision.
Recheck the bindings at acceptance. Omitting one stage is not a supported fast path.

The historical `parse_two_pass_review` without root/task_id only checks shape.
It must never be used that way on an accepting path; the runtime review gate binds
root and task, and the preserved reference guard stays composable only after its
pinned reference identity verifies. The original reference/smoke.py
does not exercise the high-risk challenge or provider-selection APIs; instructions
requiring those checks are covered by the runtime suite, not by that smoke.

The shipped focused suite reproduces, against the real CLI path: duplicate writer;
checkout-scope claims across task IDs; PID/birth-identity refusals; orphan/ambiguous
claim with owner adjudication; live continuation; command/argument drift; post-GREEN
candidate drift; forged ledger records; symlink escape; log overflow; missing/invalid/
duplicate observer receipts; terminal nonzero; multiline stdin delivery with
receiver-bound acknowledgment; build-last pack drift; stale audit; invalid inner
audit verdict; fallback refusal; failed acceptance; and complete-fingerprint
nondeterminism. Each case drives `python -m agent_loop` in an isolated fixture
project, not a validator called directly by a test.
