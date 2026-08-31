---
name: measured-performance
description: Optimize an explicitly requested performance outcome or a measured bottleneck with a correctness oracle and comparable before-after evidence; not speculative cleanup.
---

# Measured performance

Name the owner-visible delay/resource cost and freeze representative safe inputs,
environment and a correctness oracle. Measure the same statistic over comparable repeated
runs; preserve noise and unsuccessful results. Use simple timing/profiling first.

Target the largest measured bottleneck. Remove redundant work before adding caching or
concurrency. New complexity must earn its cost without changing results, safety, locking,
provenance or failure behavior. Run the oracle after each behavior change.

Continue only while gains remain material and proportionate within task authority.
Do not impose an arbitrary optimization-round count on a progressing task. Stop for
noise-level gains, exhausted useful hypotheses, correctness regression or new authority.

Report baseline, after, repetitions/statistic, absolute/relative change and limitations.
Context bytes, provider tokens, money and model quality are different metrics. Do not
infer any of the latter from byte counts or synthetic timing alone.
