# Verification scope — 2026-08-31

This is a chronological delivery summary under LOCAL_INTEGRITY, not an independent
trust domain or self-validating release receipt. It separates the historical starter,
the executable runtime, frozen external audits and subsequent repairs. A verdict only
covers the exact package hashes supplied to that auditor.

## Environment and historical reference

Windows, Python 3.14.5. Tests need only the standard library. The original six reference
members plus reference/manifest.json remain byte-identical to the first audit archive.

| Original preparation check | Actual result | Limit |
|---|---|---|
| `python -I -S -B reference/smoke.py` at package root | exit 0, AGENT_LOOP_SMOKE: PASS | Synthetic evidence only |
| `python -I -S -B ../reference/smoke.py` from examples/ | exit 0, same PASS | Working-directory independence, not another OS |
| Isolated corrupted reference core | exit 2, MEMBER_IDENTITY_MISMATCH before import | Injected exception did not execute; original bytes untouched |
| Original final archive inventory | 43 files | Superseded by repaired inventory, old archive retained |

Historical archive SHA-256:
`e5d0c4fdfe4b636909e5db63ac302cadaf453f95b06b152d382c8f72d80c47a0`.
An early preparation scan covered 41 files; it was not the final 43-file inventory.
Current package scanning must use the current manifest, not that early count.

## Independent audit of that historical archive

The owner requested two auditors. The external Claude CLI, invoked through its `opus`
alias, reported **claude-opus-4-8**, not the subsequently clarified Opus 5 requirement.
The owner allowed this already-running audit to finish. It had tools disabled and no
actual tool calls; its textual imitation of a file write is not evidence of a real write.
The separately tasked Sol auditor verified package identities and reviewed statically;
its profile did not permit test execution. The parent executed the counterexamples.

Both audits supported a private manual-mode pilot, not publication or a complete
automatic runtime. Parent adjudication selected the material review-parser defects:
duplicate PASS/FAIL declarations could accept by first match; an unknown finding ID
could disappear without requiring a correction. Both were reproduced against the
original public reference API. Documentation findings included installation layout,
reviewer skill evidence and honest scan/guarantee scope.

Those audits bind the OLD archive. They do not automatically approve repaired bytes,
and the Opus 4.8 record must never be relabeled Opus 5. The original raw audit artifacts
remain private local evidence, excluded from this distribution.

## Separate GLM repair and regression evidence

Engineer requested: **zai-coding-plan/glm-5.3-flash**, explicit **max** variant, through
the real external OpenCode route in an isolated working copy. Served model identity
remains `UNKNOWN` without machine-readable provider proof. This is not an internal
Codex engineer renamed GLM. One engineer session was continued sequentially only after
the preceding host process terminated; original logs and archive were retained.

The first attempt ended with a model output-length event and no code edits. It was not
treated as completed delivery or proof of depleted account quota. A narrowed continuation
produced the adapter; the parent authored documentation separately. A subsequent repair
addressed parent-reproduced and independently identified grammar gaps, not speculative
hardening or an arbitrary retry count.

| Phase | Exact command in isolated package root | Observed result |
|---|---|---|
| First RED, against legacy behavior | `python -I -S -B -m unittest discover -s tests -v` | 16 tests, 10 failures; actual duplicate-verdict/unknown-finding acceptance reproduced |
| First GREEN, initial adapter | Same command | 16 tests, all PASS |
| Original reference after first repair | `python -I -S -B reference/smoke.py` | PASS |
| Parent challenge of first adapter | Bound public review API with valid synthetic proof | Indented finding, star-list finding and missing Findings section incorrectly returned no refusals |
| Independent Sol static review of first adapter | Read-only source/identity review, no tests | FIX_REQUIRED; parsing mismatch, missing sections, ambiguous structure |
| Second RED, existing adapter | `python -I -S -B -m unittest discover -s tests -v` | 26 tests, 9 failures including those real gaps |
| Second GREEN | Same command | 26 tests, PASS; not final acceptance |
| Parent challenge of second adapter | Historical PASS section before real FAIL, valid synthetic proofs | Incorrectly returned no refusals; traced to guard/legacy section mismatch |
| Third RED | Same unittest command | 28 tests, 3 failures; two substantive historical-section bypasses plus tightened ambiguity expectation |
| Third GREEN | Same unittest command | 28 tests, PASS; original smoke PASS |
| Parent verification of frozen third candidate | Same unittest command and original smoke | 28 tests PASS and smoke PASS; historical/indent/table/missing-section challenges refused |
| Parent + independent Sol challenge | Canonical PASS followed by star-list FAIL | Third candidate still returned no refusals; same-seam malformed field detection required repair |
| Fourth RED | Same unittest command | 31 tests, 7 failures/subtest failures |
| Fourth GREEN | Same unittest command | 31 tests PASS; original smoke PASS |

Intermediate GREEN was not treated as acceptance. Exact current grammar,
bindings and remaining gate responsibilities are in [REVIEW_GUARD](REVIEW_GUARD.md).

## Final candidate checks

The fourth external run ended normally with exit 0. The parent froze a new review
inventory without overwriting previous evidence. Independent Sol verified all 52 members
of that local review bundle, statically reviewed the final delta, found no remaining
material issue in the repaired gate and confirmed prior repairs were retained.
Its reviewer profile did not run tests; parent execution is recorded separately.
The previously reviewed model-economy documentation had no material findings.

| Final check | Actual result | Limit |
|---|---|---|
| Parent: focused unittest suite on frozen final candidate | 31 tests PASS | Synthetic test scope only |
| Parent: original reference smoke on frozen final candidate | PASS | No real acceptance or provider invocation in smoke |
| Parent: six malformed second FAIL variants with real synthetic proof artifacts | All refused; clean baseline passed | Star/plus/numbered/plain/lowercase/space-before-colon cases |
| Independent Sol final delta review | No material findings in repaired bound-review gate | Static review, not full runtime approval |
| Parent: same focused suite and smoke in assembled package root | 31 tests PASS; smoke PASS | Reviewed executable bytes preserved on copy |
| Repaired distribution inventory | 48 files: 47 manifest members plus manifest | Private audit package, not a public release |
| Bounded secret/personal-path patterns on that inventory | PASS, no matches | Not exhaustive secret certification |
| Local Markdown link existence | PASS across 39 Markdown files | Does not validate external sites or semantic correctness |
| Simple skill frontmatter/name/description subset | PASS for 9 skills | Not full YAML/native discovery validation |

Reviewed adapter SHA-256:
`d68d6eb8f609365503b5c5624b3d0a27e4db6df00240ada100786ea1f18b43eb`.
Reviewed tests SHA-256:
`d5196cf8949bbd15ffd39a0a437446aa1e1a50b60095d0c89dbb2faece7747cf`.
Both files were copied byte-for-byte from the reviewed candidate. The packaging helper
rechecks the current allowlist/patterns/links while assembling the archive and compares
every ZIP entry byte-for-byte with its intended member. Its external local receipt
carries the final archive digest; putting that archive's own digest inside it would be
self-referential. Old archive and review bundles remain unchanged. Audit scratch files,
raw provider logs and local packaging scripts are not distributed.

## Skill-format limitation

The skill-creator quick validator could not run because PyYAML was absent from both
checked interpreters; no dependency was installed merely for this check. The deliberately
simple frontmatter receives a narrow local name/description/header check instead.
This is not full YAML validation or proof every host discovers/applies the skills.

## Accepted real nonweather pilot and starter preparation

The earlier repaired 48-file archive (SHA-256
`7316e891836f8f496391306944ca2a7a6070e42e4a7998bc1d3716a667358c7b`)
was used in an isolated Lineclean project. This is real instruction installation and
task execution on Windows/Python 3.14.5, not the synthetic reference smoke. It is not a
pilot of subsequently edited documentation or of runtime features still marked PORT.

The separate external Flash-requested engineer installed 44 package assets byte-exact,
preserved existing rules/inputs and completed a small UTF-8 line-processing utility.
Relevant skill reads are present in the local event log. The parent independently reran
17 tests and checked seven function cases, seven stdin cases, CLI errors, file input and
input preservation. A fresh Sol session first recovered the task from saved memory,
then reviewed the frozen candidate and raw evidence without writing or executing tests.
Observer was NONE; no always-on cheap model was needed for this bounded task.

The reviewer found LC-01, an incorrect code-unchanged claim across stub RED and completed
implementation. Document-only repair corrected the actual checkpoint sequence. Final
independent review passed both contract compliance and adversarial validity; R1–R5
converged with no remaining material requirement. Owner acceptance followed in the
conversation and is recorded separately against the immutable final freeze, SHA-256:
`38fca02cd87c82009dc1a5d738d0c960b4c1a920231d1664e1661ce251c7323e`.
The freeze covers 104 candidate files and six final-run evidence artifacts. Earlier
tests are linked evidence; they were not rerun by the document-only final engineer.
The frozen task/state still show the pre-review handoff; the later external review and
owner record do not rewrite those historical bytes or imply automatic acceptance.

The pilot also exposed multiline task truncation through a private Windows batch
wrapper. Receiver-side session data, not merely the outgoing arguments, showed 53 of
3886 intended characters delivered. The same native executable subsequently received
the entire body inside one added quote pair. A private guard has three passing local
regressions; independent Sol reviewed it statically. The helper is not distributed.
Earlier network failures remain unexplained. A CLI repeatability test is not presented
as CLI idempotence; function idempotence has a separate real test.

During starter preparation the parent rechecked all 104 candidate and six final-run
evidence identities with no drift, all 35 captured source anchors with no drift, and
reran the package's 31 focused tests plus reference smoke successfully. Public-facing
changes carry these lessons and the full-runtime roadmap; executable/skill/reference
bytes are unchanged. Packaging results and any new independent delta-review verdict
belong to the new archive's external receipt, not the old audits above. Private raw
logs, receiver data, acceptance record and helper scripts remain outside distribution.
This summary is LOCAL_INTEGRITY reporting, not an independently signed public transcript.

## Runtime continuation and current boundaries

- No native automatic skill/profile discovery test or executed one-tool-only pilot;
  the real pilots used separate external engineer and reviewer sessions.
- No Linux/macOS execution evidence.
- The runtime ships process claims, supervised command launching/native handoff,
  observer receipts, repair packs, lifecycle, review and acceptance gates. It does not
  install provider CLIs, authenticate provider accounts or make a universal model
  choice; configured routes remain host-specific.
- No measured token/cost/quota saving. MODEL_ECONOMY describes policies and measurement.
- Synthetic smoke/quickstart actors are not independent reviewers. The real provider
  pilot proves one Windows route, not universal quality or every provider integration.
- Source regression suites were mapped, not run against the active source project.
- MIT is the selected public license; see LICENSE and PROVENANCE. A packaged document
  cannot prove Git upload, remote CI or downloaded bytes. Those are external release
  receipts bound to the published commit/archive.

The first exact runtime archive audited by Opus 5 received PASS. A later candidate,
after additional route-identity hardening, was offered to Opus 5 first and received a
terminal 429 quota response. Only then did an exact-same-package Sol fallback audit run;
it found three material defects: forgeable/incomplete audit-route evidence, installer
ownership-path escape through links, and missing live-input revalidation before a
repair launch. Those findings were repaired with focused regressions. Parent challenge
then found and closed one remaining semantic gap: quota facts must be derived from the
bound raw error bytes, route requested/observed identities must agree, and the complete
quota evidence chain is revalidated before fallback. The repaired bytes require a new
exact-package independent audit; an earlier PASS never transfers across changed bytes.

That next exact-package Opus 5 audit independently reproduced all prior repairs but
found one further material acceptance seam: a writer could temporarily remove the
configured primary, record an honest UNKNOWN-model PASS, restore the original config
bytes, and pass the old digest-only acceptance check. A RED control/bypass regression
reproduced the issue. Acceptance now re-derives current policy and revalidates the
audit package, result bytes, route identity and any quota chain before writing an
acceptance record. These changed bytes again require a fresh exact-package audit.

Continuation 8 (2026-09-03, this working copy) repaired the three release-check-9
integrity findings. Release-check-9 had passed 232 tests and all six Windows/Ubuntu/
macOS CI jobs, but the exact-package Sol fallback audit returned FIX_REQUIRED; Opus 5
had been attempted first on the same package and returned an observed-model terminal
HTTP 429. The portability changes themselves passed audit. Repairs, each with focused
RED→GREEN regressions on the real CLI path: (1) `run --stdin-file`/`--basis-file` now
resolve through the containment primitive as regular non-link files under documented
caps (stdin 8 MiB, basis 1 MiB) before any claim/run exists, and ENGINEER stdin must
be a digest-verified task-authorized pack (context pack or manifest-bound repair pack)
passing the conservative secret scan; (2) envelope verification derives the exact
expected member/skill sets from the live task contract and recomputes the aggregate
candidate digest, so removal, addition, duplication, byte-count forgery and
candidate-digest forgery refuse before review seal or acceptance; (3) audit package,
repair pack and context pack verifiers re-render expected bytes from manifest-bound
live inputs and require byte equality (exact task/iteration, unique complete ordered
member sets, fixed audit-input roles, per-member bytes/hashes, totals, framing, no
unlisted bytes), with
synchronized inner-content + outer-hash tamper regressions for all three package
types. Parent review then reproduced and repaired two adjacent synchronized-tamper
cases: reordered audit inputs and an invented audit role. Observed locally on Windows/
CPython 3.14: focused file 117 tests OK,
full suite 262 tests OK (3 honest symlink skips), reference smoke PASS, offline
quickstart PASS. The changed bytes require a new exact-package independent audit;
no earlier PASS transfers.

Continuation 9 (2026-09-03, this working copy) closed three release-check-11
launch/audit completeness gaps returned by an exact-package independent Sol fallback
audit; Opus 5 was attempted first on the same immutable package and machine-observed
`claude-opus-5` returned a terminal HTTP 429 with zero tokens. Continuation-8 repairs
remain mandatory and unweakened. Each repair has a real RED→GREEN regression on the
real CLI path: (D1) a required audit package must carry the exact candidate closure
derived from the canonical live task plus the current frozen envelope — the task
contract, every frozen candidate member (allowlist plus report), every required skill,
and the decisive frozen validation evidence paths — with identical identity, roles and
order at build, verify, audit record and acceptance; task-only, member-missing and
relabelled declarations refuse, a closure-omitting manifest refuses verification, and
an auto-derived mode builds the whole closure when the caller declares nothing (and
re-verifies the envelope first), so caller authority is removed rather than duplicated;
(D2) ENGINEER stdin now runs the full read-only pack verification at the prelaunch
boundary: a synchronized context-pack suffix with an updated outer hash and live-member
drift refuse with `CONTEXT_VERIFY_REFUSED` and no timing/state mutation, while a repair
pack is admitted only when the current attempt binds exactly that
`progress.pack_iteration`, the write-once verification receipt still binds the current
pack+manifest bytes, and the full read-only re-render passes — all before any
claim/run/child artifact; the positive repair-stdin fixture now opens a real
pack-bound verified attempt instead of weakening the gate; (D3) `--stdin-file`/
`--basis-file` enforce the byte cap on the bytes actually read (one open reads at most
cap+1 bytes), so a growth race between the size check and the read cannot return more
than the documented cap; a controlled growing-reader regression observed RED (65 bytes
returned over a 64-byte cap) on the old two-step behavior. Observed locally on Windows/
CPython 3.14: focused file 133 tests OK (3 honest symlink skips) after 12 intended RED
failures (including the parent-reproduced synchronized envelope/package omission),
full suite 278 tests OK (3 honest skips), reference smoke PASS, offline
quickstart PASS. The changed bytes require a new exact-package independent audit;
no earlier PASS transfers.

The release manifest lists distribution paths, stored bytes and SHA-256. Bounded
patterns cannot certify absence of all secrets. Raw development logs and independent
messages remain outside the package; this summary is not a signed transcript. Validate
the archive against its release manifest before any transmission.
