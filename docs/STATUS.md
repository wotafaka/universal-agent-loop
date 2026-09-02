# Delivery status

Prepared 2026-08-31; updated the same day with the owner-authorized full-runtime
implementation (UAL-RUNTIME-1). Owner selected a starter-first release, preserving the
full-runtime objective. The isolated Lineclean pilot passed independent review and was
accepted by the owner. The owner selected the name universal-agent-loop, attribution
Вадим Захаров and MIT. The actual GitHub upload and downloaded-byte verification are
separate release steps.

## Runtime edition (candidate-local status)

The owner authorized one engineering pass over the four runtime work packages. The
result is a new `agent_loop/` package (standard library only) with a CLI
(`python -m agent_loop --project <root> ...`), focused CLI-level regressions under
`tests/`, and an offline quickstart. After independent pre-review batch 1
(REVIEW_BATCH_1.md, B1–B9) and parent counterexample batches PB01–PB12, the runtime
now composes: a trusted local authority config with registered role sessions gating
every engineer launch, owner-only adjudication and acceptance, attempt-scoped
same-task repair, native/manual handoff with owner-attested terminalization,
byte-bound context closure and measured feedback consumed by the next attempt or
task. Engineering evidence is retained outside the public package. One byte-frozen
candidate passed an independent Opus 5 audit and a fresh nonweather GLM 5.3 Flash/max
pilot on 2026-09-02; later audited hardening changed the bytes, so that PASS is
historical, not transferable. The pilot used the candidate runtime to take a separate Lineclean
change from 5 expected RED failures to 22/22 GREEN, followed by a separate runtime
validation and parent check. It proves one real Windows/provider path, not universal
quality, cross-platform execution, or measured token savings. Owner acceptance and
remote GitHub verification remain separate release steps.

| Capability | Status in this package | Important boundary |
|---|---|---|
| Preflight task schema, ambiguity and coverage gates | Executable (`agent_loop.taskfile`, CLI `task-validate`) | LOCAL_INTEGRITY; not an OS sandbox |
| Trusted authority config, role sessions, launch gate | Executable (`agent_loop.authority`, CLI `session register`, gate inside `run`/`handoff issue`) | Local consistency, not authentication; config drift reverified at review/acceptance |
| Checkout-scope writer claims, birth identity, owner adjudication | Executable (`agent_loop.claims`, `prockid`) | No lifetime claim cap; only per-record/dir bounds; unsupported platforms refuse |
| Supervised child runs, allowlisted env, bounded persisted logs, receiver ack | Executable (`agent_loop.runner`) | Overflow truncates the log on disk and is never counted evidence; stdin is fed under supervision; `--stdin-file`/`--basis-file` are contained non-link regular files under hard caps read before any claim/run, and ENGINEER stdin must be a task-authorized pack passing the secret scan |
| Attempt-scoped same-task repair | Executable (`agent_loop.attempts`, CLI `attempt open`) | Repair requires closed frozen predecessor with negative seal, changed basis + material claim, acknowledged efficiency decisions |
| Exact validation fence, fingerprints, capture binding, close order | Executable (`agent_loop.validation`, `lifecycle`) | Events count only through CLI ingestion; transcript completeness stays UNKNOWN unless a verified host export exists |
| Candidate envelope, review gate, convergence, challenge, acceptance | Executable (`agent_loop.envelope`, `reviewgate`) | FULL reviews are convergence-bound; LIGHT stays usable; seal binds a configured REVIEWER session distinct from the engineer; verification derives the expected member/skill sets from the live task contract and recomputes the candidate digest |
| Native/manual handoff with owner-attested terminalization | Executable (`agent_loop.handoff`, CLI `handoff issue/receive/confirm`) | Correlation is local, not external delivery; observed identity UNKNOWN; no fabricated PID/exit |
| Observer policy and receipts with raw span digests | Executable (`agent_loop.observer`) | Observed provider identity stays UNKNOWN without machine proof |
| Audit packages, inner verdict binding, fallback policy | Executable (`agent_loop.audit`) | Exit zero is never a PASS; valid FAIL never falls back; package verification re-renders the payload from manifest-bound live inputs and requires byte equality |
| Progress bases, material claims, repair packs, continuation | Executable (`agent_loop.packs`, `continuation`) | Consumed by BOTH command and native entry paths at prelaunch; pack verification re-renders the pack from manifest-bound live inputs |
| Byte-bound context packs, checkpoints, progressive retrieval | Executable (`agent_loop.context`, CLI `checkpoint`, `context retrieve`) | Compaction requires a verified phase-boundary checkpoint; retrieval stops on unchanged evidence fingerprint; pack verification re-renders the pack from index-bound live inputs |
| Measured feedback closing the loop | Executable (`agent_loop.delivery`, CLI `report checkpoint/efficiency/delivery`, `usage record`) | Verify duration, restoration and first-write are separate; unmeasured stays UNKNOWN; dispositions gate the next attempt/task |
| Installer lifecycle with ownership manifest | Executable (`agent_loop.installer`, CLI `install plan/dry-run/apply/doctor`) | Only installer-owned files are updated; unowned files are refused |
| Inventory of duplicate instructions and connectors | Executable (CLI `inventory`) | Defaults to zero external connectors |
| Offline quickstart exercising the real CLI incl. repair | `examples/offline_quickstart.py` | Synthetic actors only; no provider, credential or real acceptance |
| Authentic Lineclean pilot evidence | `examples/lineclean/` (byte-preserved, verified by a focused test) | Historical evidence, not a new live run |

Legacy starter rows below describe the published starter and remain true for it.

| Capability | Status in the published starter | Important boundary |
|---|---|---|
| Provider-neutral roles, tasks, review, memory | Written procedures/templates | Not OS-enforced |
| Common skills and trigger matrix | Portable authored skills | Agents must load and apply them |
| Nonweather installation and fresh-context recovery | Lineclean pilot completed and owner accepted | One Windows pilot; not every host or automatic skill discovery |
| One-tool / multi-provider configurations | Documented examples | Development provider calls do not install these configurations |
| Contract/preflight/convergence/hash checks | Executable reference snapshot + runtime | See VALIDATION for actual runs |
| Bound review grammar and reference-identity guard | Separate adapter + focused regressions | Review/correction gate only; runtime composes the whole gate |
| Model routing and token/cost economy | MODEL_ECONOMY policy + examples | No automatic portable router or measured saving claimed |
| Public license | MIT, Copyright (c) 2026 Вадим Захаров | New grant covers this distribution; historical reference preserved |
| GitHub repository | Publication is a separate operator step | Verify the uploaded tree; local packaging is not upload evidence |

The reference is intentionally an unchanged historical internal export. It contains
source-release names, legacy paths in diagnostics and inert provider-specific route
APIs. It has no runtime dependency on the source project. Do not install its internal
model-selection API as the universal provider policy. New portable instructions and
examples live outside reference/. A later neutral API extraction needs its own tests;
silently editing the preserved snapshot would destroy its provenance. The separate
validation/review_guard.py adapter closes the audited review-grammar gaps; the runtime
review gate composes it only after the pinned reference identity verifies. See
REVIEW_GUARD and current VALIDATION.

The registry records coverage of the inspected source seams, not a proof that every
historical bug across the entire private repository has been exhaustively extracted.
Source files/tests are anchors for the runtime extraction; source regression semantics
were mapped to new CLI-level tests (see IMPLEMENTATION_REPORT.md), not claimed passing
runs of the source suites here.

Manual owner acceptance is the default. Independent role sessions reduce context
coupling but do not establish a separate OS trust domain. All local evidence here
is LOCAL_INTEGRITY. Synthetic actors in the smoke, the quickstart and the tests are
not real independent reviewers.

## Remaining work for the runtime edition

- Observe the configured Linux/macOS GitHub CI jobs and verify downloaded GitHub
  bytes after publication; local Windows evidence does not substitute for either.
- The native/manual transport stores owner-attested results with UNKNOWN transcript
  completeness; a required complete-transcript fence is enforced only when the local
  config demands it and a verified host export exists.
- Only Windows is verified locally; Linux/macOS coverage is by CI configuration
  (including the publishable-archive job), not an observed run.
- No measured token/cost/quota saving; usage receipts record only what a provider
  actually reports; MODEL_ECONOMY describes measurement policy.
- The runtime CLI does not yet integrate the nine portable skills' trigger matrix
  automatically; skills remain authored procedures the agents load (unchanged starter
  boundary), with task-level `required_skills` digested into envelopes and packs.

## Current status encoded in this candidate

Current guidance: the runtime edition is executable and locally GREEN — the
focused composed suite, the full unittest suite, the reference smoke and the
offline quickstart all pass in this checkout. A real new-runtime nonweather Flash
pilot passed. Exact-package audit status is deliberately external because a new audit
verdict would otherwise change the bytes it claims to cover. Publication still
requires an exact-package PASS (primary first, evidence-bound fallback only after
proved quota exhaustion), observed remote CI, uploaded-byte verification and the
owner release decision. The starter-era
statement below is preserved as explicitly historical, not a current claim.

Historical (2026-08-31, starter preparation): the initial release then was an
MIT-licensed starter, not a full runtime; the owner's full-runtime objective was
tracked in [TRANSFER](TRANSFER.md#full-runtime-completion-plan). Initial
documentation and snapshot preparation did not use paid runs; subsequent
owner-authorized development used external GLM Flash engineering, an independent
Sol pre-review and machine-observed Opus audits as recorded in VALIDATION, followed
by owner-authorized repair continuations. Local one-off development launchers and raw
provider logs remain excluded from distribution.
