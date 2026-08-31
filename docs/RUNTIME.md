# Optional runtime adapter contract

These are requirements for porting the advanced runtime, NOT code already shipped in
this starter. A plain Markdown install offers procedural safeguards only. Bind each
enforced claim to its implementing function and negative test before marking it active.

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
refresh → report check → engineer close. This starter has no such CLI; never invent it.
If the adapter's close is terminal, no tools after successful close, including todo tools
or a second close. A refused close does not arm that terminal boundary.

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

Send a secret-scanned immutable package bound to the exact latest candidate and task.
Verify bytes before use, and again on return. Bind verdict to package and actual route.
A successful provider process or outer AUDIT_RESULT is not an inner PASS.
No old audit may accept a repaired candidate. Multiple conflicting terminal records
require adjudication rather than selecting the convenient result.

Fallback needs explicit policy and objective provider failure. A negative valid audit
is not a fallback trigger. The example's independent Sol fallback always stays visibly
different from Opus and requires manual owner acceptance. A local package-integrity
failure is BLOCKED, not a reason to transmit to another model.

A continuation package is allowed only for a proven terminal writer and no active
claim; bind prior log/sidecar hashes, task, launch identity and last checkpoint.
Missing or drifted identity cannot be repaired by prose. Repair-pack sequencing is in
[CONTEXT](CONTEXT.md). Preserve old artifacts; new iterations do not rewrite history.

## Port acceptance tests

Required gate composition for any future accepting runtime (not implemented merely by
calling one reference function): validate task/preflight syntax AND separately reject
material ambiguity before spawn; derive actual footprint and allowed route; bind the
candidate/skill/command closure; validate execution evidence; perform bound review and
durable correction; require FULL convergence and the high-risk challenge when applicable;
validate any required latest-candidate audit; finally verify the manual owner decision.
Recheck the bindings at acceptance. Omitting one stage is not a supported fast path.

In particular, historical parse_two_pass_review without root/task_id only checks shape.
It must never be used that way on an accepting path. The repaired review adapter covers
only bound review/correction, not this whole composition. Original reference/smoke.py
does not exercise the high-risk challenge or provider-selection APIs; instructions
requiring those checks are not a claim they are covered by that smoke.

At minimum reproduce: duplicate writer; PID reuse; orphaned launcher; live-claim resume;
missing/extra/malformed receipt; profile drift; no-reader inline relay; premature close;
extra fence occurrence; different RED/GREEN command; report-only finalization vs code
mutation after GREEN; post-close tool event; stale candidate audit; invalid inner verdict;
fallback provenance mismatch; ambiguous previous progress; escaping path; changed stored
bytes; incomplete command capture. Each test must exercise the real adapter path, not
only a validator called directly by a test.
