# Installation and integration

The five-minute path does not modify your project:

```text
python examples/offline_quickstart.py
```

For real use, keep this repository or extracted release as a sidecar and point every
runtime command at the target project explicitly:

```text
python -m agent_loop --project path/to/your-project task-validate --task task.json
```

The runtime stays in this checkout; its task state is written only under the explicit
target's `.agent-loop/`. Provider CLIs and accounts are not installed or selected.

## Instruction-only copy

Verify the distribution ZIP against its release manifest before copying. Preserve that
archive and manifest separately; adaptation changes bytes and is no longer validated by
the original manifest. Do not overwrite an existing setup.

Copy README.md, LICENSE and these complete directories under the target's .agent-loop/:
docs/, skills/, templates/, examples/, prompts/, reference/, and validation/ plus tests/
when included in the repaired distribution. Keep their relative relationships intact.
Do not copy the package-development root AGENTS.md, .validation/, caches or local audit logs.

The resulting layout is:

```text
target-project/
  AGENTS.md                 existing rules + merged templates/AGENTS.md section
  CLAUDE.md                 optional pointer to the same authority
  .agent-loop/
    README.md
    LICENSE                 preserve the MIT notice with copied code/docs
    STATE.md                working copy of templates/STATE.md
    TASK.md                 working copy of templates/TASK.md
    docs/ skills/ templates/ examples/ prompts/ reference/
    validation/ tests/      bounded review adapter and regressions, if included
```

Merge templates/AGENTS.md into the target's existing instructions, preserving stronger
rules. Do not copy the package root's development restrictions as the target's operating
policy. The optional templates/CLAUDE.md points to that same root authority.

Before using the installation, check these local paths actually resolve:

- root instructions → .agent-loop/STATE.md, TASK.md and docs/SKILLS.md;
- docs/WORKFLOW.md → ../templates/TASK.md;
- docs/SKILLS.md → ../skills/*/SKILL.md;
- README.md → docs/, templates/, examples/ and prompts/;
- review adapter → its sibling ../reference/ with original pinned bytes.

Replace task placeholders with actual scope, required skills and focused local commands.
Do not confuse templates with an active approved task. Explain any unresolved material
question before a paid writer starts. Use the installed tool's actual separate-session
mechanism; instruction files alone do not prove role separation or automatic invocation.

Test with one bounded nonweather task. Record session identities, actual skill reads,
raw checks, independent review and owner decision. Running the synthetic reference or
adapter regression suite does not count as that real integration pilot. A startup that
only reads the small entrypoint/task/triggered skills is intentional; do not load every
installed file into every session.

This copy mode installs procedures and optional checks, not the Python runtime itself.
Use the sidecar command above for executable claims, launch supervision, lifecycle,
review and acceptance. Native skill discovery and provider configuration remain
host-specific steps with their own tests and permissions.

## Executable runtime quickstart

Since the runtime edition, the package also ships `agent_loop/`, an executable
standard-library CLI. Verify it works on your machine before any integration:

```text
python examples/offline_quickstart.py
```

It builds a synthetic nonweather demo project, drives the real CLI through
preflight → RED → GREEN → close → freeze → synthetic review → acceptance →
delivery report, and deletes its scratch project on exit. Synthetic actor labels
(OWNER, reviewer) are fixtures, not a real owner decision or independent review.
The runtime commands then operate on an explicit project root, for example:

```text
python -m agent_loop --project path/to/your-project task-validate --task task.json
```

Contract details and gate composition: [RUNTIME](RUNTIME.md). Everything remains
LOCAL_INTEGRITY; manual owner acceptance stays the default.

The public archive is built exclusively from `RELEASE_ALLOWLIST.txt` via
`agent_loop release build/verify` (secret-pattern gate, exact manifest, hash
verification); see [RELEASE](RELEASE.md). Portable named skills
`karpathy-guidelines` and `ponytail` ship in `skills/` and are listed in the
skills matrix; load them for software work.
