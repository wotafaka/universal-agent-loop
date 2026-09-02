# Release gates

Current guidance: the runtime edition (`agent_loop/`) is executable and locally
GREEN — focused suite, full suite, reference smoke and the offline quickstart all
pass in this checkout. A prior byte-frozen candidate passed an independent Opus 5
audit and a fresh nonweather Flash pilot; later security repairs changed the bytes,
so that verdict does not transfer. Publication requires an exact-package audit,
the owner release decision, observed remote CI, and downloaded-byte verification.
Nothing below is acceptance, and none of those gates may be skipped to meet a date.

The public archive is built exclusively from the versioned allowlist
`RELEASE_ALLOWLIST.txt` (schema `release-allowlist/1`) through the standard-library
builder `agent_loop/release.py`:

```text
python -m agent_loop --project . release build \
  --release-root . --allowlist RELEASE_ALLOWLIST.txt \
  --out-zip ual-archive.zip --out-manifest release-manifest.json
python -m agent_loop --project . release verify \
  --release-root . --allowlist RELEASE_ALLOWLIST.txt \
  --archive ual-archive.zip --manifest release-manifest.json
```

The allowlist excludes `.source/`, `.validation/`, private engineering task/report
files, caches, credentials, local profiles and the historical private
`PACKAGED_FILES.json` input manifest. The builder refuses missing, duplicate,
non-canonical, escaping or symlink members, scans every included byte sequence for
a conservative documented secret-pattern set before writing anything, writes
deterministic ZIP metadata/order, and emits an exact manifest (member bytes +
SHA-256) that `release verify` re-checks against both the archive and the current
sources. CI runs the full suite, the reference smoke and the offline quickstart
from the extracted archive bytes on Windows, Ubuntu and macOS; a local run is not
a claim that remote CI has run.

Historical checklist (explicitly dated 2026-08-31, describing the earlier
starter-only release preparation):

- Preserve the chosen name, Вадим Захаров attribution and MIT license. The owner's
  MIT grant resolves historical reference NONE/WITHHELD for this distribution;
  retain both the original bytes and the explanation in PROVENANCE.
- The reference ships as a labeled historical snapshot, not the default universal
  model router.
- The Lineclean pilot satisfied the bounded nonweather integration gate for the
  earlier repaired starter on Windows; see [VALIDATION](VALIDATION.md). It does
  not test every host, the new runtime, or any provider.
- Pattern scans are aids, not proof of complete sanitization; inspect results.
- Create a fresh repository without private source history, only after explicit
  release approval. Preserve reference bytes across Git line-ending conversion
  (.gitattributes).
- Verify the actual cloned/uploaded bytes and instructions. Export/commit/push alone
  are not evidence that users can reproduce the workflow.

Manual owner acceptance and exact data-transmission scope remain the default for new
adopters. New license/notices or other release edits require a fresh allowlist, a
rebuilt archive and manifest, and review of the actual delta; an earlier private ZIP
is not automatically the licensed release.
