---
name: test-driven-change
description: Establish genuine RED then GREEN for new or changed executable behavior and reproduced bug fixes; documentation-only work is exempt.
---

# Test-driven change

Name the observable missing behavior. Write the smallest test with independently derived
expectations and run it before implementation. The observed failure must be the intended
defect, not a broken import, syntax error or unavailable fixture. A passing test is not RED.

Make the smallest behavior change, repeat the same reproduction and run focused adjacent
checks. Keep exact command/cwd/output/exit and candidate identity for both phases. Honor
an installed runtime's declared occurrence fence; unexpected extra runs need a corrected
task/iteration, not hidden command substitution.

Mock only unavailable, slow or privileged boundaries. Exercise real project behavior,
not source strings or the presence of mocks. Do not weaken expectations or swallow errors
to manufacture GREEN. Tests added after implementation are regression tests, not TDD proof.

Pure documentation, unchanged copied assets and generated metadata can state an explicit
exemption. Unsafe or irreproducible external behavior needs a deterministic fixture at the
nearest safe boundary; no live credentials or irreversible operations just to get RED.
