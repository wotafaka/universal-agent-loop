# Source-to-package transfer registry

Source paths below are private-source anchors, not links required by adopters. Their
snapshot hashes live in SOURCE_SNAPSHOT.json. Source tests were located, not executed
here. Current package runs are recorded only in VALIDATION.md.

Labels: **REF** = executable unchanged reference; **GUIDE** = portable procedure/skill;
**PORT** = advanced runtime still to extract; **DOMAIN** = deliberately conditional;
**EXCLUDE** = must not export. A PORT row is not an implemented feature.
**GUARD** = separately authored executable adapter around the unchanged REF, not a
complete acceptance/runtime implementation.

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

| ID | Source feature / anchor | Destination | Status / check or remaining work |
|---|---|---|---|
| C01 | Two authority axes, B16 §2 | WORKFLOW | GUIDE; permissions never inferred from capabilities |
| C02 | Local vs independent evidence, B16 §1/3 | WORKFLOW, STATUS | GUIDE; separate session not separate trust domain |
| C03 | Lifecycle vs evidence state, C | reference, WORKFLOW | REF; synthetic transition negatives |
| C04 | Candidate/task/skill closure, B16 §6 + M | RUNTIME, reference | REF demo + PORT actual closure |
| C05 | Final validation bound to bytes, F/M | RUNTIME, LESSONS | PORT; test_validation_capture_excludes_exactly_the_implementation_report |
| C06 | Complete invocation and output proof, F/M | RUNTIME | PORT; explicit cwd/argv/env/exit/truncation/footprint |
| C07 | Seed applied vs merely declared, F/C | RUNTIME, LESSONS | PORT; producer and consumer contradiction tests |
| C08 | Actual-fingerprint nondeterminism, C | reference, RUNTIME | REF; conflicting comparable outcomes rejected |
| C09 | Two-pass proof-based review, C | reference, validation/review_guard.py, evidence-review | REF + GUARD + GUIDE; exact grammar and bound proof regressions, real reviewer still required |
| C10 | Reviewer-owned high-risk challenge, C/R | evidence-review, WORKFLOW | GUIDE + PORT acceptance gate |
| C11 | Durable correction records, C + lessons | LESSONS, REVIEW_GUARD, REVIEW template | REF + GUARD + GUIDE; malformed findings refuse instead of disappearing |
| C12 | Stored-byte hash/no implicit normalization, C/E | reference manifest, .gitattributes | REF; positive and tamper smoke |
| C13 | Verify before core import, E | reference/smoke.py, validation/review_guard.py | REF + GUARD; pinned manifest/member tamper checks before reused import |
| C14 | Latest-candidate audit + review seal, M/A | RUNTIME | PORT; recheck on acceptance, not only review |
| C15 | Role flip cannot bypass acceptance, M | RUNTIME, multi-provider example | PORT; owner default, no inherited delegation |
| C16 | Git unavailable ≠ clean diff, B16 §6 | WORKFLOW | GUIDE; explicit candidate inventory |

## Runtime and recovery

| ID | Source feature / anchor | Destination | Status / check or remaining work |
|---|---|---|---|
| X01 | Pre-spawn claim, L | RUNTIME | PORT; refuse duplicate before child |
| X02 | Host/PID/process birth identity, L | RUNTIME | PORT; PID reuse and ambiguous claim tests |
| X03 | Terminal release/owner adjudication, L/M | RUNTIME | PORT; no automatic stale cleanup |
| X04 | Direct durable logs + atomic sidecar, L | RUNTIME | PORT; output integrity and bounded growth |
| X05 | Session ID retained after tool yield, B15 | RUNTIME, LESSONS | GUIDE; never launch twice from lost UI state |
| X06 | Bounded child environment/overlay, L/M | RUNTIME | PORT; ambient env never quietly inherited |
| X07 | Exact occurrence lifecycle fence, M/L | RUNTIME, TASK, test-driven-change | GUIDE + PORT; startup separated, final RED returns to architect |
| X08 | Post-successful-close tool ban, M/L | RUNTIME | PORT; later tool events rejected |
| X09 | Read-only observer parent continuation, B15 | loop-workflow, RUNTIME | GUIDE; no concurrent lifecycle mutation |
| X10 | Observer NONE/DEFERRED/IMMEDIATE, R | RUNTIME, CONTEXT | GUIDE + PORT; test_low_routine_strong_clear_work_needs_no_observer |
| X11 | Receipt identity/profile hash/timing, R/M/L | RUNTIME | PORT; test_new_shape_receipt_binds_the_real_observer_profile |
| X12 | Inline raw evidence if no reader, B15 + L13 | RUNTIME, LESSONS | GUIDE; paths alone fail evidence delivery |
| X13 | Terminal receipt resnapshot, L | RUNTIME | PORT; child can end before heartbeat |
| X14 | Stable substantive progress basis, R/L | CONTEXT | PORT; test_equal_bases_duplicate_and_changed_bases_progress |
| X15 | Structured material-progress claim, R/L | CONTEXT | PORT; test_identical_post_baseline_claim_is_non_authorizing |
| X16 | Monotonic run IDs, ambiguous previous record, R/L | CONTEXT, RUNTIME | PORT; no invented clean baseline |
| X17 | Hash-bound terminal continuation, M/L | RUNTIME | PORT; no live sidecar/claim continuation |
| X18 | Repair-pack build-last/verify-first, M/B15 | CONTEXT, loop-workflow | GUIDE + PORT; hash-drift fallback |
| X19 | Audit package/result integrity, A/M | RUNTIME | PORT; candidate and package identity required |
| X20 | Objective provider fallback, A/M | multi-provider, RUNTIME | GUIDE + PORT; valid FAIL is not outage |
| X21 | Invalid inherited Windows stdin handle, L12 | RUNTIME, LESSONS | GUIDE; preserve spawn-boundary regression when porting |
| X22 | Full task delivery at actual receiver, Lineclean pilot | LESSONS, single-tool example | GUIDE + PORT; child spawn/requested argv alone is not delivered-content proof; private wrapper fix is not shipped runtime |

## Context, economics, preflight

| ID | Source feature / anchor | Destination | Status / check or remaining work |
|---|---|---|---|
| P01 | Compact hash-linked startup, R/M/B16 §15 | CONTEXT, entrypoint template | GUIDE + PORT generator |
| P02 | History on demand, conflict triggers, B16 §15 | CONTEXT | GUIDE; originals preserved, not silently discarded |
| P03 | Stable prefix/task delta handoff, B15 | CONTEXT | GUIDE; no unmeasured caching claim |
| P04 | Provider bindings separate from role/authority, R | WORKFLOW, MODEL_ECONOMY, examples | GUIDE; source-specific code inert in reference |
| P05 | Flash first / full only with evidence, R/B15 | multi-provider, MODEL_ECONOMY | GUIDE example, never universal model requirement; cost and tokens measured separately |
| P06 | Measured delivery feedback into next task, T/M | CONTEXT, templates | GUIDE + PORT closed-loop generator |
| P07 | Successful delivery vs terminal writers, T/M | CONTEXT | PORT; terminal nonzero ≠ review-ready |
| P08 | LIGHT/FULL + material clarification stop, C/R | reference, TASK, WORKFLOW | REF + GUIDE; portable template distinct from legacy grammar |
| P09 | Conservative actual footprint, R/M/L | WORKFLOW, RUNTIME | GUIDE + PORT; test_facts_can_never_weaken_the_derived_footprint |
| P10 | Requirement coverage + convergence, C | reference, TASK/REVIEW | REF + GUIDE; exact frozen IDs |
| P11 | No retry/token/time cap while progressing, R/B15 | WORKFLOW, CONTEXT | GUIDE; explicit user/host limits remain binding |
| P12 | Compact root and durable learnings, linked upstream | entrypoint, LESSONS | GUIDE; no copied 5-iteration cap |

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

This registry is intentionally explicit about PORT rows. They are the remaining work
for a full automatic runtime edition. Shipping this starter as if those rows were already
implemented would be a defect. Further extraction should use these source anchors and
their tests instead of recreating the protocols from memory.

## Full-runtime completion plan

Owner decision: publish a useful starter first, then retain the complete mapped general
workflow as the target. These are implementation work packages, not four mandatory
ceremonies for every end-user task. No runtime package below is complete yet. Existing
REF/GUARD code and GUIDE rules are starting assets, not proof of an installed runtime.

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
   Those suites have not been ported or executed here. This registry covers inspected
   seams, not a certified inventory of every historical private incident.
4. Demonstrate the assembled path on a new nonweather project, including genuine
   independent-context review, crash/repair recovery and an honest unavailable-route
   case. Keep one-tool operation useful without an external-model dependency.
5. Claim automation only for tested paths. Platform support and token/cost savings
   need their own measured evidence. Optional expensive layers must stay optional.

The compact root/on-demand context and durable-correction ideas from the earlier
external workflow remain P12/C11. Spec Kit's useful intent, clarification and convergence
ideas remain P08–P10, without installing a second specification bureaucracy. Provenance
and non-copied upstream boundaries are in [PROVENANCE](PROVENANCE.md).
