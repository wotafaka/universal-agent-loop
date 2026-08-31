---
name: capture-integrity
description: Preserve source identity, time semantics and visible gaps when integrating external collectors, parsers, reconnects or capture storage.
---

# Capture integrity

Identify endpoint, schema, units, timezone, ordering and documented rate behavior.
Keep raw identifiers/payload identity distinct from normalized values. Unknown fields
or undocumented source substitutions remain unknown.

Separate event, receive and persist time plus sequence/cursor. Preserve original time
semantics when normalizing; never silently replace missing event time with receive time.
Define stable event identity before writing. On reconnect, prove the resumed cursor or
record a gap; process liveness and nonempty files do not prove continuity.

Exercise duplicate, out-of-order, stale, malformed and reconnect cases with safe frozen
fixtures. Track parser-version changes and rejects. Use data-footprint-safety for durable
writes and isolated bounded storage for tests. Report actual coverage and gaps explicitly.
