---
name: focused-engineering
description: Keep software design, implementation and review scoped to a verifiable user outcome; use before adding abstractions, dependencies or unrelated refactors.
---

# Focused engineering

Before nontrivial changes, state material assumptions and the observable success check.
Read the actual caller-to-effect path, then reuse an existing helper or native facility
before creating another layer. Prefer standard-library mechanisms when sufficient.

Every changed line must serve the requested outcome. Do not add a framework, cache,
background worker or configuration surface for a hypothetical future need. Match local
conventions and preserve unrelated edits. Investigate the shared owning boundary before
patching only one caller's symptom.

Simplicity never removes validation, security, data-loss handling, accessibility or
explicit requirements. Confirm behavior with the smallest relevant executable check.
For code changes use the project's TDD procedure. Defer cosmetic debt explicitly rather
than generating another repair round. Explain meaningful tradeoffs, not speculative ones.
