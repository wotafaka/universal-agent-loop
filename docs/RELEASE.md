# Release gates

This release checklist covers the MIT-licensed starter after an owner-accepted pilot,
not a completed runtime port. Do not upload the whole development folder blindly.
Chosen name: universal-agent-loop. Attribution: Вадим Захаров. Root LICENSE is the current grant;
the superseded private export status is explained in PROVENANCE without rewriting it.

Before publication:

1. Preserve the chosen name, Вадим Захаров attribution and MIT license. Confirm the actual target
   account and public/private visibility before publishing. The owner's subsequent MIT
   grant resolves historical reference NONE/WITHHELD for this distribution; retain both
   the original bytes and the explanation of the new grant in PROVENANCE.
2. Audit the complete intended file allowlist, notices, example bindings and the remaining
   provider-specific reference API. Decide whether historical reference ships separately
   or a tested neutral API replaces it for public distribution. This starter includes
   it as a labeled historical reference, not the default universal model router.
3. Run the instructions on a real isolated nonweather pilot. A synthetic smoke is not
   this integration test. Confirm skills are actually read and roles actually separated.
   The Lineclean pilot satisfies this bounded gate for the earlier repaired starter on
   Windows; see [VALIDATION](VALIDATION.md). It does not test every host or later runtime.
4. If shipping automatic supervision, implement and test the adapter contract first.
   Otherwise explicitly publish as an instruction/template starter, not turnkey runtime.
   The owner selected starter-first. Remaining automation is tracked in TRANSFER;
   do not drop PORT items or rename them complete to meet a release date.
5. Run focused checks and independent review; freeze the reviewed files with hashes.
6. Scan only the allowlisted release files for secrets, private paths and unwanted data.
   Pattern scans are aids, not proof of complete sanitization; inspect results and examples.
7. Create a fresh repository without private source history, only after explicit release
   approval. Exclude .validation, local evidence, credentials, temporary files and caches.
   Preserve reference bytes across Git line-ending conversion (.gitattributes).
8. Verify the actual cloned/uploaded bytes and instructions. Export/commit/push alone
   are not evidence that users can reproduce the workflow.

A target-project installation and authorized development-provider runs occurred in the
isolated pilot. No generic provider runtime was installed. Record the actual remote,
commit and downloaded-byte check outside the frozen artifact when publication occurs;
this checklist alone never proves that upload happened.
Manual owner acceptance and exact data-transmission scope remain the default for new
adopters. New license/notices or other release edits require a fresh manifest and review
of the actual delta; an earlier private ZIP is not automatically the licensed release.
