# Instruction-only installation

Verify the original distribution against PACKAGED_FILES.json before copying. Preserve
that original distribution and its manifest separately; adaptation changes bytes and
does not remain validated by the original manifest. Do not overwrite an existing setup.

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

This installs procedures and optional checks, not a launcher, process lock or automatic
acceptance system. Native skill discovery, provider configuration and runtime integration
remain host-specific steps with their own tests and permissions.
