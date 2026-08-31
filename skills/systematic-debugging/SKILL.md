---
name: systematic-debugging
description: Diagnose reproduced failures, regressions or unexpected runtime behavior before choosing a code fix or repair iteration.
---

# Systematic debugging

Capture the exact failure, input, command, state and identity. Separate broken code from
expected guard refusal, an incorrect task, stale evidence and an unavailable environment.
Do not weaken a correct guard to compensate for malformed instructions.

Trace the symptom back through callers to the first invalid transition. Form one
falsifiable mechanism and test the smallest distinguishing case. Preserve raw evidence;
logs must not disclose secrets. If reproduction is unsafe, use an isolated fixture or
report the evidence gap.

Repair at the owning shared boundary, checking affected callers. No blind retries,
arbitrary sleeps, broad catches or silent defaults. Use state-based waiting where possible.
For code fixes require genuine RED/GREEN and an adjacent negative case. A progressing
repair has new material evidence or a falsified hypothesis, not merely a new timestamp.

Record defect → cause → protection with evidence. Different repeated failures can indicate
a flawed design; reconsider the mechanism instead of stacking speculative patches.
