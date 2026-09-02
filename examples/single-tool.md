# One tool, separate contexts

Example task: add a pure filename-normalization function to a small local utility.
No weather, markets, external service or paid second subscription is needed.

1. Architect session inspects the existing utility and defines the desired mapping,
   collision behavior and focused checks. It names scope and applicable skills.
2. Start a separate engineer session using whatever independent-session mechanism the
   installed tool actually offers. Supply task, necessary source and skills, not the
   architect's entire chat. Engineer alone edits and captures RED/GREEN.
3. Start a fresh reviewer session with task, final candidate and raw evidence. Reviewer
   challenges Unicode/collision behavior when relevant; it does not modify the candidate.
4. Route material findings back to the engineer and review the changed candidate. Owner
   accepts the exact reviewed result. Save concise state and a reproducible lesson.

The same model may serve all three roles. Context separation does not guarantee different
reasoning or independent trust domains. If the host cannot create distinct contexts,
use ordinary tests and explicitly report self-review; don't claim independent audit.

This is an integration scenario, not a test execution log. The packaged executable
runtime demo is `examples/offline_quickstart.py`; `reference/smoke.py` separately
checks the preserved historical contracts. Both use synthetic actors.

## Real nonweather pilot: Lineclean

Separately, we tested installation in an isolated standard-library Python line-cleaning
utility on Windows. This was a multi-provider pilot, not an executed Codex-only or
Claude-only certification. Its process can be adapted to the one-tool scenario above.
No private paths, session logs or pilot source files are distributed here.

The bounded task was to remove repeated complete lines while preserving order, case
and spaces; accept UTF-8 file/stdin input; write LF-terminated output to stdout without
changing the input; reject invalid input with a nonzero exit. The contract covered:

| Requirement | Actual check |
|---|---|
| R1: preserve project rules and install starter | 44 installed assets matched the starter; existing root rules and protected inputs preserved |
| R2: line semantics | Function cases, blank lines, Unicode and stable order |
| R3: CLI boundary | stdin/file input, UTF-8 failures, missing file and input preservation |
| R4: genuine validation | Observed stub RED, implementation, disclosed test-oracle corrections, then 17 passing tests; parent reran checks |
| R5: truthful report and recoverable memory | Fresh reviewer recovered goal, requirements, status and next step from files before reading code/history |

External Flash was the requested engineer; independent Sol reviewed a frozen candidate
read-only. The requested model is not independent proof of the served model. Observer
was NONE. Relevant skills were read, not all nine indiscriminately. Review found a real
reporting defect: code had changed from stub to implementation, although the report
claimed otherwise. The engineer corrected documents; the independent delta review
passed with R1–R5 converged, and the owner accepted the pilot.

Another defect was in the private launch path: a Windows batch wrapper delivered only
53 characters of a 3886-character repair task. The same native executable received the
complete task body inside one added pair of quotes. Receiver-side evidence verified the
body; a local regression now rejects that lossy multiline wrapper path before launch.
That lossy private wrapper is not shipped. The portable runtime uses supervised stdin
delivery plus receiver acknowledgement instead.

One CLI test named idempotence actually checked repeatability. That limitation is
disclosed; function idempotence was separately tested. Earlier network errors remain
unexplained and must not be attributed to the later prompt-delivery defect.

### Ask your agent to reproduce the process

Use [INTEGRATE](../prompts/INTEGRATE.md) with this addition:

> Follow the Lineclean pilot's process, not its provider names or local paths. Preserve
> my existing rules, define a small task with explicit success checks, record the skills
> actually read, use a separate engineer context and fresh read-only reviewer if my host
> supports them. Have the reviewer recover the task from saved files before reading the
> implementation. Preserve actual failed and passing evidence, fix material findings,
> and ask me to accept the exact reviewed candidate. Do not claim this proves token
> savings. If separate contexts are unavailable, report that
> limitation instead of calling self-review independent.

See [VALIDATION](../docs/VALIDATION.md) for evidence scope and historical package binding.
