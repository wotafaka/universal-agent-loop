# Offline quickstart — the real runtime, no models

This is the one short executable path promised in the README. It drives the
actual `agent_loop` CLI through one complete governed cycle on a synthetic
nonweather project (a tiny line utility) inside this checkout, including a
bounded synthetic ENGINEER claim and a same-task negative-review repair
attempt:

```text
python examples/offline_quickstart.py
```

Expected output (abridged):

```text
[ual] 1. task preflight (material ambiguity and coverage checked)
[ual] 2. RED — reproduce the missing behavior first
[ual] 3. the smallest change; the SAME command repeats as GREEN
[ual] 4. SYNTHETIC engineer claim: gated launch, birth identity, terminal release
[ual] 5. report, refresh, report-check, close, freeze envelope
[ual] 6. SYNTHETIC reviewer FAILS attempt 1; repair opens attempt 2
[ual] 7. attempt 2: RED, fix, GREEN, close, refreeze
[ual] 8. SYNTHETIC positive review, owner acceptance, feedback
OFFLINE_QUICKSTART: PASS (synthetic actors; no provider, no credential)
```

What this proves and what it does not:

- Proven: the portable CLI path works end to end with only the Python
  standard library on this machine — trusted authority config and
  registered synthetic sessions, gated engineer launch with checkout-scope
  claim and OS birth identity, the exact RED→GREEN occurrence fence,
  close-order enforcement, write-once envelope freezing with byte digests,
  a negative review opening a same-task repair attempt (changed progress
  basis plus a structured material claim), a positive bound review, and an
  acceptance decision bound to the exact reviewed candidate.
- Not proven: any model behavior, provider route or real acceptance.
  `OWNER`, `ENG-SYNTH` and `REV-SYNTH` are SYNTHETIC fixture labels inside
  one local run, never a real owner decision or an independent review. A
  genuine model-backed example and its reviewed artifacts are supplied
  separately (see the authentic [Lineclean](lineclean/README.md) pilot); a
  review PASS is not owner acceptance.

The demo project is created under `examples/.scratch/` and deleted on
exit. See [docs/RUNTIME.md](../docs/RUNTIME.md) for the enforced
contracts and [examples/single-tool.md](single-tool.md) for the real
one-tool integration scenario with separate sessions.
