# Agent-Loop Core — Private Export

Minimal, standard-library-only export of the weather-research-platform
agent-loop authority/evidence core for **private owner review**.

## What this is

`agent_loop_contract.py` is the pure, stdlib-only validation vocabulary of
the internal delivery loop: the `TaskLifecycle` and `EvidenceState`
vocabularies with fail-closed transition validation, the risk-adaptive
`## Intent preflight` task contract (deterministic LIGHT/FULL derivation,
fail-closed requirement → success criterion → validation command coverage,
and the material-ambiguity pre-spawn boundary), the flash-first
engineer-selection route gate, the two-pass review gate with the
evidence-bound `## Convergence disposition`, durable-correction
dispositions, fingerprint-based nondeterminism classification, and the
canonical byte/hash policy. It is copied byte-for-byte from the
source release; the exact SHA-256 and byte length of every exported file
are pinned in `manifest.json`.

`smoke.py` is a reference script that demonstrates, with **synthetic
reference evidence only**, the whole loop:

    candidate -> intent preflight -> validation -> frozen envelope ->
    two-pass evidence, durable correction and review convergence ->
    review passed -> explicit manual owner decision

through a provider-neutral reference acceptance gate, and it proves the
failing cases: tampered member or proof bytes, missing required evidence,
equal comparable fingerprint conflicts, implementer self-acceptance,
review-only-as-acceptance, absent or non-accepting explicit decisions,
implementer/reviewer actors with an otherwise valid reviewed candidate,
candidate or proof drift on the acceptance path, an understated or
materially ambiguous intent preflight, and an unconverged accepting review
are all rejected.
Before anything is imported, the smoke verifies the complete known member
inventory and the byte identity of every copied member against
`manifest.json` (verify before use), so a corrupted or incomplete copy
fails closed without executing any copied module. Some accepted core
capabilities are source-internal — for example the flash-first
engineer-selection route gate; the portable reference never exercises
them, and they stay inert here.

## Manual acceptance and independent review

- A passed review is a review outcome. It is **never** acceptance.
- Acceptance is an explicit manual decision by the owner, bound to the
  exact reviewed candidate. No engineer, reviewer, auditor, or the smoke
  itself can accept a task: the reference acceptance gate refuses absent,
  non-owner, and non-accepting decisions even when every other artifact
  verifies.
- Independent review means a second party recomputed or re-executed the
  evidence (the `validation-review-proof/1` records with their own artifact
  digests), not that review prose exists.

## Running the smoke

From this directory, inside an unrelated fixture project:

    python -I -S -B smoke.py

`-I` runs the interpreter isolated (no environment variables, no site
packages, no `.pth` path processing), `-S` skips site initialization, and
`-B` prevents `.pyc` writes. The smoke uses only the Python standard library
and the copied core; it never calls a provider, never reads the source
repository, and never touches credentials, network, or local state beyond a
temporary directory it removes afterwards.

## Source and license origin

| File | Origin |
|---|---|
| `agent_loop_contract.py` | exact bytes of `tools/agent_loop_contract.py` @ `weather-v0.9.106-risk-adaptive-intent-preflight-convergence` |
| `README.md` | authored by `weather-v0.9.106-risk-adaptive-intent-preflight-convergence` |
| `TASK.md` | authored by `weather-v0.9.106-risk-adaptive-intent-preflight-convergence` |
| `REVIEW.md` | authored by `weather-v0.9.106-risk-adaptive-intent-preflight-convergence` |
| `EXPORT_AUDIT.md` | authored by `weather-v0.9.96-agent-loop-slice5-private-export` |
| `smoke.py` | authored by `weather-v0.9.106-risk-adaptive-intent-preflight-convergence` |

No public license was found in the source repository at export time. This
export is for **private owner-review use only**: no license is granted, and
redistribution or publication rights are NOT cleared. Publication is a
separate, explicit owner decision and is withheld here; a withheld
publication is an honest boundary, not a silent pass.

## Guarantee level

All evidence produced or verified through this export is `LOCAL_INTEGRITY`:
it is produced and checked on one owner-controlled machine and account. It
protects against confused agents, stale context, drift, missing evidence,
and self-reported success. It does NOT protect against a hostile process
running under the same OS account, and `INDEPENDENT_EVIDENCE` is never
claimed without a separate trust domain.
