# Source-to-package transfer registry

Source paths below are private-source anchors, not links required by adopters. Their
snapshot hashes live in SOURCE_SNAPSHOT.json. Source tests were located, not executed
here. Current package runs are recorded only in VALIDATION.md.

Labels: **REF** = executable unchanged reference; **GUIDE** = portable procedure/skill;
**PORT** = advanced runtime extracted into the runtime edition; **DOMAIN** = deliberately
conditional; **EXCLUDE** = must not export. **GUARD** = separately authored executable
adapter around the unchanged REF, not a complete acceptance/runtime implementation.

The owner-authorized runtime edition (`agent_loop/` + `tests/`) is an engineering
candidate under LOCAL_INTEGRITY. A real Windows/provider pilot passed; exact-package
audit/publication/CI evidence remains external and hash-bound rather than inferred
from this document.
Every runtime binding below names the implementing module/CLI command and the focused
regression file that exercises the real CLI path in isolated fixture projects.

Source abbreviations:

- C: tools/agent_loop_contract.py; tests/test_agent_loop_contract.py.
- R: tools/agent_loop_routing.py; tests/test_agent_loop_routing.py.
- L: tools/run_external_glm.py; tests/test_external_glm_launcher.py.
- M: tools/project_memory.py; contract tests and tests/test_project_memory.py.
- A: tools/run_external_audit.py, tools/build_external_audit_package.py;
  tests/test_external_audit_launcher.py and tests/test_external_audit_package.py.
- T: tools/analyze_delivery_timing.py; tests/test_delivery_timing.py.
- E: tools/export_agent_loop_core.py; tests/test_agent_loop_export.py.
- F: tools/run_focused_tests.py; contract capture tests.
- B15/B16: BRAIN/15_INTEGRATED_EXTERNAL_DELIVERY_WORKFLOW.md /
  BRAIN/16_AGENT_LOOP_VNEXT_AUTHORITY_AND_EVIDENCE_CONTRACT.md.

## Contracts and evidence

| ID | Source feature / anchor | Destination | Starter disposition | Runtime binding (module · CLI · tests) |
|---|---|---|---|---|
| C01 | Two authority axes, B16 §2 | WORKFLOW | GUIDE; permissions never inferred from capabilities | `config.route_check` honest UNAVAILABLE; `envelope.accept` owner-actor binding · CLI `route check`, `accept` · test_task_and_route, test_envelope_review_accept |
| C02 | Local vs independent evidence, B16 §1/3 | WORKFLOW, STATUS | GUIDE; separate session not separate trust domain | Every envelope carries `guarantee_level: LOCAL_INTEGRITY` · `envelope.freeze_envelope` · test_envelope_review_accept |
| C03 | Lifecycle vs evidence state, C | reference, WORKFLOW | REF; synthetic transition negatives | Ported vocabulary + transitions `lifecycle.TASK_STATUSES/TRANSITIONS` · CLI `status set` · test_progress_pack_continuation |
| C04 | Candidate/task/skill closure, B16 §6 + M | RUNTIME, reference | REF demo + PORT actual closure | `envelope.freeze_envelope/verify_envelope` bind task bytes, skills and members · CLI `envelope freeze/verify` · test_envelope_review_accept |
| C05 | Final validation bound to bytes, F/M | RUNTIME, LESSONS | PORT; capture excludes exactly the report | `validation.capture_digest` excludes exactly `candidate.report`; report still bound in envelope · CLI `validate record`, `close` · test_fence_close |
| C06 | Complete invocation and output proof, F/M | RUNTIME | PORT; explicit cwd/argv/env/exit/truncation/footprint | `runner.run_child` sidecar (ual-run/1) with argv, env identity, exit, log digests, truncation · CLI `run` · test_claims_and_runner |
| C07 | Seed applied vs merely declared, F/C | RUNTIME, LESSONS | PORT; producer and consumer contradiction | `validation.record_occurrence` refuses `VALIDATION_SEED_MISMATCH` · CLI `validate record --seed` · test_fence_close |
| C08 | Actual-fingerprint nondeterminism, C | reference, RUNTIME | REF; conflicting comparable outcomes rejected | `validation.classify_pair` + rejected_conflicts block close · test_fence_close |
| C09 | Two-pass proof-based review, C | reference, validation/review_guard.py, evidence-review | REF + GUARD + GUIDE; real reviewer still required | `reviewgate.validate_review` bound proof records; composes the pinned reference guard on demand · CLI `review validate --reference-root` · test_envelope_review_accept |
| C10 | Reviewer-owned high-risk challenge, C/R | evidence-review, WORKFLOW | GUIDE + PORT acceptance gate | `reviewgate._challenge_errors` for HIGH-risk reviews · test_envelope_review_accept |
| C11 | Durable correction records, C + lessons | LESSONS, REVIEW_GUARD, REVIEW template | REF + GUARD + GUIDE; malformed findings refuse | `reviewgate._correction_errors` with task `lessons_path` · test_envelope_review_accept |
| C12 | Stored-byte hash/no implicit normalization, C/E | reference manifest, .gitattributes | REF; positive and tamper smoke | `hashing.sha256_hex/member_digest` over exact stored bytes; write-once evidence · test_fence_close, test_envelope_review_accept |
| C13 | Verify before core import, E | reference/smoke.py, validation/review_guard.py | REF + GUARD; pinned manifest/member tamper checks | Runtime composes the guard only via `reviewgate._compose_reference_guard` (identity verified inside) · test_envelope_review_accept |
| C14 | Latest-candidate audit + review seal, M/A | RUNTIME | PORT; recheck on acceptance, not only review | `envelope.accept` rechecks seal + audit bound to current envelope · CLI `accept` · test_audit, test_envelope_review_accept |
| C15 | Role flip cannot bypass acceptance, M | RUNTIME, multi-provider example | PORT; owner default, no inherited delegation | `envelope.accept` refuses non-owner actors (`ACCEPTANCE_ACTOR_NOT_OWNER`) · test_envelope_review_accept |
| C16 | Git unavailable ≠ clean diff, B16 §6 | WORKFLOW | GUIDE; explicit candidate inventory | Envelope records explicit member inventory and `git.claimed: false` · `envelope.freeze_envelope` · test_envelope_review_accept |

## Runtime and recovery

| ID | Source feature / anchor | Destination | Starter disposition | Runtime binding (module · CLI · tests) |
|---|---|---|---|---|
| X01 | Pre-spawn claim, L | RUNTIME | PORT; refuse duplicate before child | Checkout-scope `claims.acquire` before any child; refusal leaves no run dir · CLI `claim acquire`, `run --purpose ENGINEER` · test_claims_and_runner |
| X02 | Host/PID/process birth identity, L | RUNTIME | PORT; PID reuse and ambiguous claim tests | `prockid.process_start_identity` (Win GetProcessTimes / Linux procfs / macOS `ps lstart`) bound into claims · CLI `claim bind-child/release` · test_claims_and_runner |
| X03 | Terminal release/owner adjudication, L/M | RUNTIME | PORT; no automatic stale cleanup | `claims.release` (terminal proof + log identity), `claims.abandon` (owner reason); nothing auto-deletes · test_claims_and_runner |
| X04 | Direct durable logs + atomic sidecar, L | RUNTIME | PORT; output integrity and bounded growth | `runner.run_child`: exclusive log, atomic ual-run/1 sidecar, declared byte cap, overflow flag · test_claims_and_runner |
| X05 | Session ID retained after tool yield, B15 | RUNTIME, LESSONS | GUIDE; never launch twice from lost UI state | `run --session-id` stored in sidecar and continuation record · `continuation.prepare` · test_progress_pack_continuation |
| X06 | Bounded child environment/overlay, L/M | RUNTIME | PORT; ambient env never quietly inherited | `runner._build_env` allowlist ∩ ambient + declared overlay; env policy digest in fingerprint · test_claims_and_runner |
| X07 | Exact occurrence lifecycle fence, M/L | RUNTIME, TASK, test-driven-change | GUIDE + PORT; startup separated, final RED returns to architect | Ledger enforces declared order/counts/outcomes (RED→GREEN), extra/unexpected refuse · CLI `validate record` · test_fence_close |
| X08 | Post-successful-close tool ban, M/L | RUNTIME | PORT; later tool events rejected | `POST_CLOSE_RUN/RECORD/EVENT` refusals after `lifecycle.close` · test_fence_close |
| X09 | Read-only observer parent continuation, B15 | loop-workflow, RUNTIME | GUIDE; no concurrent lifecycle mutation | Observer receipts are read-only evidence; gate refuses missing/invalid at close · `observer.gate_errors` · test_observer |
| X10 | Observer NONE/DEFERRED/IMMEDIATE, R | RUNTIME, CONTEXT | GUIDE + PORT; low routine strong clear needs none | `observer.decide_observer_policy` (unknown facts fail closed) · CLI `observer policy` · test_observer |
| X11 | Receipt identity/profile hash/timing, R/M/L | RUNTIME | PORT; new receipt binds the real observer profile | Receipts bind task+run+terminal state; span digests verify raw log bytes · `observer.record_receipt` · test_observer |
| X12 | Inline raw evidence if no reader, B15 + L13 | RUNTIME, LESSONS | GUIDE; paths alone fail evidence delivery | Span digest mismatch refuses close (`OBSERVER_RECEIPT_INVALID:span digest mismatch`) · test_observer |
| X13 | Terminal receipt resnapshot, L | RUNTIME | PORT; child can end before heartbeat | Close binds receipt digests; envelope rechecks them (`OBSERVER_RECEIPT_DRIFT`) · test_observer |
| X14 | Stable substantive progress basis, R/L | CONTEXT | PORT; equal/duplicate/changed bases | `packs.stable_progress_basis` + gate · CLI `progress check` · test_progress_pack_continuation |
| X15 | Structured material-progress claim, R/L | CONTEXT | PORT; identical post-baseline claim is non-authorizing | `packs.material_claim_identity` + state-recorded identity · test_progress_pack_continuation |
| X16 | Monotonic run IDs, ambiguous previous record, R/L | CONTEXT, RUNTIME | PORT; no invented clean baseline | Malformed prior sidecar refuses `PROGRESS_PRIOR_RECORD_MALFORMED`; write-once records/sequences · test_progress_pack_continuation |
| X17 | Hash-bound terminal continuation, M/L | RUNTIME | PORT; no live sidecar/claim continuation | `continuation.prepare/verify` binds sidecar/log/task bytes; live claim refuses · test_progress_pack_continuation |
| X18 | Repair-pack build-last/verify-first, M/B15 | CONTEXT, loop-workflow | GUIDE + PORT; hash-drift fallback | `packs.build_pack/verify_pack` write-once, task drift → `FULL_CANONICAL_STARTUP` fallback payload · test_progress_pack_continuation |
| X19 | Audit package/result integrity, A/M | RUNTIME | PORT; candidate and package identity required | `audit.build_package/verify_package` bind envelope + deterministic payload; tamper refuses · test_audit |
| X20 | Objective provider fallback, A/M | multi-provider, RUNTIME | GUIDE + PORT; valid FAIL is not outage | `audit.record_audit`: exit zero is not PASS; FAIL never falls back; policy+objective failure only · test_audit |
| X21 | Invalid inherited Windows stdin handle, L12 | RUNTIME, LESSONS | GUIDE; preserve spawn-boundary regression | Stdin is fed through a pipe (`subprocess.PIPE`), never an inherited handle; spawn failures recorded as SPAWN_FAILED · `runner.run_child` · test_claims_and_runner (multiline stdin) |
| X22 | Full task delivery at actual receiver, Lineclean pilot | LESSONS, single-tool example | GUIDE + PORT; requested argv alone is not delivered-content proof | Receiver-bound `ual-ack/1` (run id + task + stdin digest); multiline body verified byte-exact · `runner._verify_ack` · test_claims_and_runner |

## Context, economics, preflight

| ID | Source feature / anchor | Destination | Starter disposition | Runtime binding (module · CLI · tests) |
|---|---|---|---|---|
| P08 | LIGHT/FULL + material clarification stop, C/R | reference, TASK, WORKFLOW | REF + GUIDE; portable schema distinct from legacy grammar | `taskfile.validate_task` + `material_ambiguity` refuse BLOCKED/open IDs pre-spawn · CLI `task-validate` · test_task_and_route |
| P09 | Conservative actual footprint, R/M/L | WORKFLOW, RUNTIME | GUIDE + PORT; facts never weaken derived footprint | `taskfile.derive_candidate_footprint/footprint_refusals` (weaker route, governance authority) · test_task_and_route |
| P10 | Requirement coverage + convergence, C | reference, TASK/REVIEW | REF + GUIDE; exact frozen IDs | FULL coverage rows mapped to commands/criteria; `reviewgate._convergence_errors` · test_task_and_route, test_envelope_review_accept |
| P01 | Compact hash-linked startup, R/M/B16 §15 | CONTEXT, entrypoint template | GUIDE + PORT generator | `context.build_pack/verify_pack` with per-member SHA-256 index and measured verify time · CLI `context build/verify` · test_context_delivery |
| P02 | History on demand, conflict triggers, B16 §15 | CONTEXT | GUIDE; originals preserved, not silently discarded | Packs/packs digests point at canonical originals; pack carries digest-only manifest · `packs.build_pack` · test_progress_pack_continuation |
| P03 | Stable prefix/task delta handoff, B15 | CONTEXT | GUIDE; no unmeasured caching claim | Pack layout: required skills first (prefix), task body last (delta) · `context.build_pack` · test_context_delivery |
| P04 | Provider bindings separate from role/authority, R | WORKFLOW, MODEL_ECONOMY, examples | GUIDE; source-specific code inert in reference | `config.load_config/route_check`: local neutral bindings, absent → honest UNAVAILABLE · CLI `route check` · test_task_and_route |
| P05 | Flash first / full only with evidence, R/B15 | multi-provider, MODEL_ECONOMY | GUIDE example, never a universal model requirement | Runtime ships no default model; role classes and transports only (`config.ROLE_CLASSES`) · test_task_and_route |
| P06 | Measured delivery feedback into next task, T/M | CONTEXT, templates | GUIDE + PORT closed-loop generator | `delivery.efficiency_report` one-per-task, measured fields, UNKNOWN otherwise · CLI `report efficiency` · test_context_delivery |
| P07 | Successful delivery vs terminal writers, T/M | CONTEXT | PORT; terminal nonzero ≠ review-ready | `delivery.delivery_report` requires acceptance record; counts terminal-nonzero runs separately · test_context_delivery |
| P11 | No retry/token/time cap while progressing, R/B15 | WORKFLOW, CONTEXT | GUIDE; explicit user/host limits remain binding | Progress gate blocks duplicates, authorizes changed bases; no attempt counter anywhere · `packs.progress_gate` · test_progress_pack_continuation |
| P12 | Compact root and durable learnings, linked upstream | entrypoint, LESSONS | GUIDE; no copied 5-iteration cap | Task `lessons_path` bound by correction dispositions; no copied cap · `reviewgate` · test_envelope_review_accept |

## Skills and exclusions

| Source | Portable destination | Disposition |
|---|---|---|
| weather-research-workflow | loop-workflow | GUIDE; remove repository-only startup command |
| Karpathy / Ponytail local skills | focused-engineering | GUIDE; authored combined procedure, not full upstream redistribution |
| weather-test-driven-development | test-driven-change | GUIDE; observed RED and explicit exemptions |
| weather-systematic-debugging | systematic-debugging | GUIDE; guard refusal vs defect distinction |
| weather-invariant-and-property-testing | invariant-testing | GUIDE; genuine oracle only |
| weather-evidence-based-performance | measured-performance | GUIDE; remove obsolete two-round cap per owner direction |
| Two-pass independent review + skill application evidence | evidence-review | GUIDE; separate reviewer, bound evidence and material findings |
| weather-data-footprint-safety | data-footprint-safety | GUIDE; bounded writes/replay/cleanup preserved |
| weather-source-and-capture-integrity | capture-integrity | GUIDE; timestamps/identity/gaps preserved |
| weather-research-integrity + walk-forward-validation | DOMAIN-EXTENSIONS | DOMAIN; conceptual obligations, not a complete portable science pack |
| weather-trading-capital-safety | DOMAIN-EXTENSIONS | DOMAIN; not a generic live-trading implementation |
| Owner profile / credentials / raw logs / journals / archives | None | EXCLUDE; private and not needed by adopters |
| Weather/market rules and source-specific PnL gates | Domain implementation stays private | DOMAIN; no imposed trading objective for unrelated projects |
| Private automatic owner acceptance | Manual default; opt-in design example | EXCLUDE as default; authority cannot be exported |

All nine portable skills are preserved unchanged in this edition. Tasks bind their
`required_skills` by digest into envelopes and repair packs; automatic trigger loading
remains a host-side procedure (see STATUS "Remaining work").

This registry is explicit about which PORT rows became executable in the runtime
edition and which stay GUIDE. The edition is a reviewed-pending candidate; treating a
test PASS as owner acceptance would be a defect. Further source extraction should use
these source anchors and their tests instead of recreating the protocols from memory.

## Full-runtime completion plan

Owner decision: publish a useful starter first, then retain the complete mapped general
workflow as the target. These are implementation work packages, not four mandatory
ceremonies for every end-user task. The runtime edition above now implements packages
A–D as one candidate; the acceptance evidence below still requires independent review,
a real nonweather pilot and owner acceptance before any package is called done.

| Package | Registry IDs owned | Minimum acceptance evidence |
|---|---|---|
| A — neutral task, validation and acceptance boundary | C01–C16, P08–P10 | Real task/candidate/skill closure; exact invocation capture; malformed/stale/tampered evidence refuses; two review passes and owner acceptance stay separate; unimplemented required audit paths refuse |
| B — single writer and process recovery | X01–X08, X14–X17, X21–X22 | Duplicate writer refused before spawn; PID reuse/crash/ambiguous claim cannot clear ownership; full task reaches actual receiver; exact occurrence fence and post-close boundary; existing process survives UI/session yield without duplicate launch |
| C — context, memory and measured feedback | P01–P03, P06–P07, P11–P12, X18 | Fresh-context task recovery; hash drift refuses stale repair pack; build-last/verify-first; meaningful-progress continuation without arbitrary attempt caps; successful delivery distinguished from terminal failure; measured advice acknowledged in next task |
| D — optional model, observer and audit bindings | P04–P05, X09–X13, X19–X20 | One-tool and external-provider bindings keep independent role contexts; actual route/provenance recorded; unavailable route is honest; observer receives raw evidence; final audit is bound to latest candidate and correct verdict; no silent provider substitution |

Keep all nine skills and their trigger/application evidence through A–D. Domain safety
remains an explicit extension, not deleted merely to make a generic default smaller.
Owner profiles, credentials, private history and default delegated acceptance remain
excluded as listed above. The public workflow must not require the original project,
its trading objective, an external engineer subscription or any particular model.

Completion rule for the full edition:

1. Every C/X/P ID has a final disposition with portable destination, runnable check or
   evidence, and review binding. Preserve IDs and old dispositions; do not silently
   delete a feature, turn PORT into GUIDE, or treat a renamed status as completion.
   Any changed scope must be explicit and owner-approved.
2. Mechanically compare each source anchor's bytes/hash before porting. At this starter
   preparation, all 35 SOURCE_SNAPSHOT members matched their captured identities. A
   later source delta requires a targeted reconciliation, not replacement from memory.
3. Reconcile the regression cases at each mapped seam, not only the prose summary.
   The runtime edition maps those seams to new CLI-level tests (IMPLEMENTATION_REPORT.md);
   the source suites themselves have not been ported or executed here.
4. Demonstrate the assembled path on a new nonweather project, including genuine
   independent-context review, crash/repair recovery and an honest unavailable-route
   case. Keep one-tool operation useful without an external-model dependency. The
   offline quickstart demonstrates the mechanism with synthetic actors; the genuine
   model-backed pilot remains parent-owned work.
5. Claim automation only for tested paths. Platform support and token/cost savings
   need their own measured evidence. Optional expensive layers must stay optional.

The compact root/on-demand context and durable-correction ideas from the earlier
external workflow remain P12/C11. Spec Kit's useful intent, clarification and convergence
ideas remain P08–P10, without installing a second specification bureaucracy. Provenance
and non-copied upstream boundaries are in [PROVENANCE](PROVENANCE.md).
