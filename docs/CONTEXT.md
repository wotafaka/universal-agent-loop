# Context, memory and cost control

## Small mandatory start

Read the compact project entrypoint, current task in full, small binding rules and the
complete bodies of triggered skills. Inspect raw evidence needed for the current decision.
Keep historical narrative and unrelated skills on demand. Do not remove a safety rule
solely because it is long. On contradictory state, critical ambiguity or hash drift,
read the exact authoritative original; a summary never resolves its own contradiction.

Current state contains task/status, evidence pointers, blockers and next action. Decisions
explain non-obvious choices. Lessons record reproduced defects and protections. History
is preserved separately; current state must not grow into another complete history.
Generated context is derivative and is regenerated, not hand-edited into authority.
Record exact bytes/digests of indexed originals if claiming a hash-linked context pack.

## Compact handoff

Supply task and role, scope/exclusions, candidate identity, necessary files, triggered
skill bodies, exact focused checks, raw evidence and open findings. Never substitute
engineer conclusions for those artifacts. A role gets its own bounded context, not all
preceding conversations. Stable common instructions form the prefix; task delta is last.
This ordering may help caching but does not guarantee provider cache hits.

## Hash-bound repair pack

Architect finishes bookkeeping first, freezes the repair batch/touched-file map and builds
the write-once pack LAST. Pack includes complete task and skills, exact fixes, source
positions, validation budget and canonical-document manifest. No state refresh between
building and engineer verification: that would invalidate the pack's own hashes.

Engineer verifies first, before edits. Verification re-renders the pack bytes from the
manifest-bound live inputs and requires byte equality, so a synchronized manifest+pack
edit cannot pass as verified. A verified pack replaces repeated historical
reading, not safety obligations. On mismatch use full canonical startup and re-establish
current authority; never work from a failed pack. Closeout bookkeeping resumes only at
the declared end. Do not call a legacy startup command first when it itself refreshes
and invalidates the supplied pack.

## Progress-backed repeats

Compare substantive candidate/evidence/hypothesis state, not iteration numbers, task
titles, timestamps, log/pack paths or generated-state bytes. A changed textual repair
batch alone is insufficient: bind stable finding IDs and a material-progress reason
to real evidence. Unknown or unreadable previous records are not a convenient empty
baseline. Keep migration handling explicit and don't rewrite legacy records.

## Model economy

Plain-language guide, role table and single-tool alternative:
[Как мы экономим модели и токены](MODEL_ECONOMY.md).

Use deterministic commands for file inventories, hashes and test execution. Use a small
model only for tiny immutable clerical packages; a routine observer may summarize bounded
logs. Preserve high-quality architect decisions and independent risk-appropriate review.
Engineer selection uses demonstrated capability, task difficulty and oracle strength,
not file count, model branding or quota panic. No silent downgrade.

Measure context-restoration time, time to first write, run duration, supplied bytes,
known token usage, validation and audit time. Unknown values stay UNKNOWN, not estimates.
The source project's compact-context recommendation requires BOTH restoration >=300s
and >=25% of completed wall time. This is an example calibrated policy, not a universal
law and not a token limit. A large context/session alone is not a defect or restart trigger.

Delivery feedback stays bounded: one current summary per task, no ever-growing polling
history. Record the measured bottleneck; choose apply-next-task or no-action with reason.
Carry actionable decisions into the next task and verify they were applied. Terminal
writers with no successful delivery cannot produce a review-ready success summary.

For a pilot compare similar tasks: wall time, actual usage if available, number of
material defects, review rework and restoration cost. Never trade away a missed material
defect for an impressive byte-reduction percentage. No claimed savings until measured.
