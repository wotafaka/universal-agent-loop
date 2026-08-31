# Transferable incident lessons

Source anchors: BRAIN/LESSONS_LEARNED.md L1–L13 and BRAIN/16 sections 6–17.
These are sanitized lessons, not original incident records or claims of enforcement here.

| Failure | Keep this protection | Where in package |
|---|---|---|
| Impressive proxy/result hides bad input or biased sample | Check source/label semantics and availability; show excluded/negative evidence | DOMAIN-EXTENSIONS |
| Several layers changed together; failure becomes unattributable | Isolate the falsifiable cause, preserve working comparison | systematic-debugging |
| Capture fields were never recorded | Missing seed/platform/candidate stays UNKNOWN; don't reconstruct from current files | RUNTIME |
| Producer claims it applied a seed but never did | Apply at execution boundary; consumer independently rejects contradictions | RUNTIME, runtime port tests |
| Same invocation hides behind different requested labels | Compare actual executable/argv/candidate/environment, not labels | RUNTIME |
| Honest incomplete capture wrongly called malformed | Zero members may be incomplete; complete requires real digest; never infer PASS | RUNTIME |
| Tests ran from a convenient but unrecorded cwd | Record actual explicit working directory on every counted invocation | templates/TASK |
| GREEN belongs to older candidate bytes | Freeze and compare final capture per command; report exception is explicit, not general | WORKFLOW, RUNTIME |
| Snapshot copy treated as publication/acceptance | Export changes neither license nor authority | RELEASE, reference manifest |
| Corrupt copied core imported before verification | Verify known inventory and bytes before importing core; trust verifier separately | reference/smoke.py |
| Windows console passes invalid stdin handle to child | Diagnose spawn traceback; adapter uses a valid explicit stdin policy | RUNTIME |
| Child starts but receives only the heading of a multiline task | Verify receiver-side task content; avoid a proven lossy shell-wrapper path | TRANSFER X22; Lineclean pilot |
| Report calls stub-to-implementation bytes unchanged | Name both checkpoints and their identities; a later tests-only edit says nothing about earlier code changes | VALIDATION; Lineclean pilot |
| Two runs of original input labeled idempotence | Feed the first output back for idempotence; label repeated original input repeatability | invariant-testing; Lineclean pilot |
| Observer receives paths but cannot read them | Send actual bounded raw bytes inline; reuse observer, don't repeat failed probe | RUNTIME |
| ATTACHED receipt interpreted as proof of consumption | Separate route, evidence delivery, model observation and review guarantees | RUNTIME |
| Parent loses tool session id and starts another child | Retain/poll existing session, bind OS birth identity, respect write claim | RUNTIME |
| Startup mutates hashes in freshly built repair pack | Build pack last, verify first; full startup only after failed verification | CONTEXT |
| Startup mistakenly treated as a validation occurrence | Separate bootstrap permission from exact counted validation fence | RUNTIME |
| Different commands called RED/GREEN | Declare and repeat same reproduction command with correct occurrence count | test-driven-change |
| Extra test invocation prevents close | Fix contract before paid launch; new justified iteration after unexpected final RED | RUNTIME |
| Report uses an acceptance token in historical prose | Use copy-safe wording with raw history link; don't weaken authority lint blindly | templates/IMPLEMENTATION |
| Tools invoked after successful terminal close | No post-close planning or second close; reviewer checks actual event sequence | RUNTIME |
| Report finalized after GREEN triggers false drift | Separate executable capture set and full final envelope; exclude only declared report | RUNTIME |
| Changing repair title passes as progress | Bind stable finding/evidence/hypothesis change; timestamps/iteration never count | CONTEXT |
| Unreadable latest progress ignored in favor of older convenient record | Treat ambiguous provenance as non-authorizing | CONTEXT |
| Model/authority labels understated to allow launch | Derive conservative actual footprint; reviewer recomputes it | WORKFLOW |
| Observer always runs for trivial tasks | Risk-adaptive NONE/DEFERRED/IMMEDIATE; mechanical supervision remains | RUNTIME |
| Only engineer oracle re-run on high-risk review | Reviewer-owned counterexample or independent boundary trace | evidence-review |
| Process terminal interpreted as successful handoff | Require successful completed delivery separately from all-writers-terminal | CONTEXT |
| Audit process exits zero but inner verdict rejects | Exact inner verdict and package binding, never select a convenient wrapper result | RUNTIME |
| Required provider unavailable; fallback silently relabeled | Preserve objective reason, actual route, exact candidate and acceptance authority | examples/multi-provider |
| Current profile or audit changes after initial check | Recompute identity at accepting boundary, not only when recording | RUNTIME |
| Parser accepts the first PASS and ignores a later FAIL | One exact section and one canonical verdict; reject ambiguity | REVIEW_GUARD, focused regressions |
| Unknown or indented finding silently becomes no findings | Strict Findings grammar shared across guard and delegated validator; malformed input refuses | REVIEW_GUARD, focused regressions |
| Report says exactly-one but code checks only duplicates | Test missing, duplicate and valid sections independently | review guard regressions |
| Human review table mistaken for machine input | Separate formats explicitly; unsupported content must not silently pass | REVIEW_GUARD, templates/REVIEW |
| Owner-selected external engineer replaced by internal agent | Honor actual provider/model boundary, not just role name or separate context | package AGENTS, multi-provider |
| Model alias assumed to mean required version | Verify actual route/version; report mismatch without relabeling | multi-provider |
| Cheaper model advertised as fewer tokens | Measure task-wide cost, token usage and quality separately | MODEL_ECONOMY |

For each new material defect record cause, evidence, correction and regression. Promote
a recurring actionable lesson into a rule/test in one canonical place. Not every typo
deserves a permanent instruction or another paid audit.
