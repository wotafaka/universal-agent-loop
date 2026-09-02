---
name: ponytail
description: Minimal-dependency coding ladder for coding, design, review and dependency choice; default full intensity — prefer need, existing helpers, stdlib and native features before new code or dependencies.
license: MIT
---

# Ponytail

Conceptual origin: the "how to keep your dependencies minimal" engineering
stance publicly argued by Armin Ronacher (the "pony tail" dependence degree),
re-authored here as an original concise adaptation under MIT. Not a copy of any
external post; load it when the trigger applies.

Default intensity: full. Apply the ladder to every new dependency, helper or
layer you are about to add — in coding, design, review and dependency choice.

## The ladder, in order

1. **Need** — does the outcome actually require this capability? If not, stop.
2. **Existing helper** — does this codebase already have it? Reuse before adding.
3. **Standard library** — does the platform ship it? Prefer stdlib mechanisms.
4. **Native feature** — does the language/host give it directly (syntax, built-in
   protocol, tool switch)? Use it before pulling anything in.
5. **Installed dependency** — is an already-installed dependency sufficient?
   Use it before introducing a new one.
6. **Minimum new code** — only now write new code, and write the minimum that
   satisfies the current need without speculative options or layers.

## What simplification may never remove

Never simplify away validation, security, data integrity, error handling or an
explicit requirement. Minimal code is not less-checked code; it is less-optional
code. Guards, bounds and failure paths are part of the feature.

## In review

Ask for the ladder position of any new import, file or layer. A dependency must
name what it replaces and why steps 1–5 failed. A rewrite must name what got
simpler for the caller, not only for the author.
