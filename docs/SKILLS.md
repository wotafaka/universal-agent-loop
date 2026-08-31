# Skill selection

Read complete SKILL.md bodies only when their trigger applies. Both engineer and
reviewer use the matrix; reviewer applies it to validation decisions without gaining
candidate write authority. A report names the actual constraint and evidence, not just
the skill's filename. Merge with stronger existing project skills; do not replace them.

| Trigger | Portable skill |
|---|---|
| Begin/resume/handoff a governed implementation task | [loop-workflow](../skills/loop-workflow/SKILL.md) |
| Software design, implementation, refactor or review | [focused-engineering](../skills/focused-engineering/SKILL.md) |
| New/changed executable behavior or bug fix | [test-driven-change](../skills/test-driven-change/SKILL.md) |
| Reproduced failure or unexpected behavior | [systematic-debugging](../skills/systematic-debugging/SKILL.md) plus test-driven-change |
| A genuine invariant, round-trip, determinism or independent oracle | [invariant-testing](../skills/invariant-testing/SKILL.md) |
| Explicit performance target or measured bottleneck | [measured-performance](../skills/measured-performance/SKILL.md) |
| Reviewing a candidate or claiming completion | [evidence-review](../skills/evidence-review/SKILL.md) |
| Durable data writes, journals, retention, cleanup or migration | [data-footprint-safety](../skills/data-footprint-safety/SKILL.md) |
| External capture, parsers, timestamps, reconnects | [capture-integrity](../skills/capture-integrity/SKILL.md) |

These are standalone authored adaptations, not installations of Superpowers, Trail of
Bits, Clean Code, ByteDance or an upstream plugin. [Origins](PROVENANCE.md) distinguishes
conceptual influence from copied code. Do not claim a plugin is installed from a mention.

Research validation and real-money/credential operations require a project-specific
domain pack. See [domain boundaries](DOMAIN-EXTENSIONS.md). Weather-specific rules are
deliberately not loaded for a website, library or ordinary app.

Suggested layout after integrating: `.agent-loop/skills/` holds portable bodies;
the project's root instructions explicitly route to the matrix. Native tool-specific
discovery is optional and must be verified in that host. Copying files does not prove
automatic invocation. Do not duplicate bodies in several directories that can drift.
