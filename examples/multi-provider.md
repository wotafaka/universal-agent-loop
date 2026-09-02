# Original multi-provider pattern, sanitized

This describes the source configuration inspected for this package, not a requirement
or claim about models currently available to every account. Validate local capabilities
before use. No credentials, personal profile or original machine paths are supplied.
Why these roles are separated, when an observer is unnecessary, and how to measure
actual savings: [MODEL_ECONOMY](../docs/MODEL_ECONOMY.md).

| Role | Source example binding | Responsibility |
|---|---|---|
| Architect / final code review | Codex Sol | Scope, risk, repair decisions, decisive evidence checks |
| Engineer | OpenCode route to GLM 5.3 Flash | Sole candidate writer, implementation/tests/report |
| Exceptional engineering escalation | Full GLM 5.3 | Only after concrete task-bound Flash inability |
| Optional observer | Terra low effort | Bounded process/log observation, no writes or acceptance |
| Tiny optional clerk | Luna low effort | Immutable small clerical input, no review judgment |
| Risk-gated external auditor | Claude Opus 5 | Read-only frozen-package audit; verify exact version before launch |
| Unavailable-auditor fallback | Separate Sol session | Objective permitted fallback, truthful identity, owner acceptance |

The source engineer route uses `zai-coding-plan/glm-5.3-flash`; stronger engineering
uses `zai-coding-plan/glm-5.3`. Adaptive effort is high for routine strong-oracle work,
max for difficult/novel work; historical tasks may explicitly bind max. The task/runtime
agreement wins, not an example copied blindly. Terra example identity is `gpt-5.6-terra`.
These are configuration examples, not portable defaults or verified provider availability.

Owner clarification: this example requires Opus 5, not whichever model the alias opus
selects. A preparation audit requested that alias and the CLI reported Opus 4.8; the owner
allowed that already-running audit to finish, but it is not Opus 5 coverage. Verify the
exact required version before transmission; if unavailable, disclose it and apply only
an explicitly permitted fallback. The generic loop does not require Opus or this version.

## Dispatch pattern to reproduce

Define task and actual footprint → resolve preflight → select available role binding →
check no active writer → freeze context → acquire write-realm claim → launch ONE engineer.
Supervise mechanically; attach observer only when its policy calls for it, supplying bytes.
On terminal delivery, verify actual output and candidate → independent review → repairs
with material progress if needed → required frozen-package audit → owner acceptance.

Do not run full GLM merely because Flash has been working a long time or produced RED.
Do not ask Sol to repeatedly read routine logs when mechanical checks or a properly fed
observer suffice. Do not launch Terra only to rediscover it cannot read supplied paths.

In the source adapter an unusable provider audit can produce SOL_FALLBACK_REQUIRED.
The fallback record binds exact package, objective trigger and real Sol identity. A
valid FAIL from Opus never triggers model shopping. Local package drift blocks both routes.
The source avoids a duplicate paid Opus attempt on the same frozen package; that is an
idempotency/cost policy, not a global limit on repairs of changed candidates.

## Primary auditor -> evidence-bound fallback policy

The runtime expresses the owner's audit ordering as a configurable policy, never a
built-in default. In `.agent-loop/config.json` (trusted local authority config):

```json
"audit_policy": {
  "primary": "claude-opus-5",
  "fallback": "gpt-5.6-sol",
  "fallback_requires": "PRIMARY_QUOTA_EXHAUSTED"
}
```

With this binding the runtime enforces exactly:

1. The required audit is accepted only from the primary model `claude-opus-5`.
2. A Sol (`gpt-5.6-sol`) audit is permitted only after a machine-readable
   primary quota receipt — recorded by `agent_loop audit quota-receipt` for the
   exact frozen package (manifest+payload digests) with reason
   `PRIMARY_QUOTA_EXHAUSTED` — proves the primary had no tokens left.
3. A negative Opus verdict, a malformed result, auth/CLI/network errors, local
   package drift, an active Opus run, or preference never permit Sol substitution;
   invalid FAIL findings classify `AUDIT_RESULT_INVALID`, never fallback.
4. Acceptance requires a clean `PASS`; `CONDITIONAL_PASS` records but never
   satisfies the required-audit gate.
5. The observed auditor model comes from the bound launcher/route receipt, not
   auditor self-assertion. For a required audit with a configured primary,
   missing/unproven identity fails closed; optional ungated routes may still
   report `UNKNOWN` honestly.

Without this binding no fallback exists at all: an unavailable route is reported
honestly and the required-audit gate stays unsatisfied.

Every audit result and quota receipt carries a bound
`ual-audit-route-receipt/1` (task ID, exact package manifest/payload digests,
requested model, observed model, terminal `FINISHED` status, integer exit
code, and the exact result/raw-error file path, bytes and SHA-256). A primary
PASS additionally requires exit 0 and `requested_model == model_observed ==
claude-opus-5`. The quota receipt is minted only from a primary
`PROVIDER_FAILURE` route receipt whose structured raw provider-error evidence
(HTTP/API status 429 or an explicit provider quota code, with terminal error)
mechanically classifies as `PRIMARY_QUOTA_EXHAUSTED`; the `--reason` string is
a cross-check, never sufficient by itself. Those structured facts are parsed from
the bound raw-error JSON bytes; CLI metadata cannot invent them, and the complete
quota → route → raw chain is revalidated before a fallback result is accepted.

Public default remains manual acceptance. The source's private automatic acceptance
for explicitly delegated nonprivileged work is NOT inherited by a new project. If desired,
the owner must configure it separately, with no engineer self-acceptance and rechecks of
candidate, review, audit and role identity immediately before archive.

## Copy-ready request

Use this configuration as an example, not a hardcoded dependency. Inventory my installed
tools and available independent-session mechanisms without reading or exporting secrets.
Apply prompts/INTEGRATE.md. Map these roles to what I actually use. If I use only one
tool, preserve separate engineer/reviewer contexts within that tool. Start by running
the offline quickstart, then choose either the executable runtime sidecar or the lighter
instruction-only mode deliberately. Preserve stronger existing project safety and
acceptance rules; never claim provider integration or native skill discovery without
testing it on the actual host.
