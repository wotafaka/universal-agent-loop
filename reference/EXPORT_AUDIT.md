# Export Audit — <task id>

Member-level privacy/license/export audit of one export directory. Audit the
exact frozen inventory, never a plan; an audit never accepts a task and
never widens scope.

## Inventory

| Member | SHA-256 (recorded) | Origin recorded | Matches stored bytes |
|---|---|---|---|

- [ ] The manifest schema is the known version; the member list is sorted
      and unique; every member recomputes to its recorded byte length and
      SHA-256 over the exact stored bytes.
- [ ] Every member records its exact source/license origin.

## Privacy

- [ ] No credentials, tokens, wallet or proxy secrets, owner-profile paths,
      or auth material.
- [ ] No internal state, task history, reports, journals, generated context,
      or archive content bundled.
- [ ] Internal-only defaults (standing delegation, provider routes, owner
      context) do not leak into exported defaults.

## License and publication

- [ ] License status stated honestly (for example: none found in the source
      repository; private owner-review use only).
- [ ] No license grant, redistribution claim, or publication performed by
      the export or this audit.
- [ ] Publication remains a separate explicit owner decision; a withheld
      publication is recorded as a boundary, not hidden.

## Guarantee level

- [ ] Evidence is labeled `LOCAL_INTEGRITY`; no `INDEPENDENT_EVIDENCE` is
      claimed without a separate trust domain.

## Disposition

`AUDIT_PASS`, or findings with owners and follow-up. Non-passing audit
outcomes never gate-through: acceptance requires the exact passing terminal
evidence, never a summary of it.
