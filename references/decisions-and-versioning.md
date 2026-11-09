# Decisions, show rules, and versions

## Episode decisions

Append every proposed or human-reviewed decision to `history/decisions.jsonl`. A new decision replaces an old one through `supersedes`; the old record remains. The project manifest lists only currently active IDs.

Useful fields include stage, object type, source reference, action, reviewer status, reason, evidence, confidence, exact quote, and replacement link.

## Show rules

Episode decisions are private to the project by default. Promote only a reusable preference that the user explicitly confirms. Store it in an isolated show profile with source project and source decision IDs. Another episode must explicitly reference a rule version.

When rules conflict, the current episode's explicit human decision wins. Never promote quotes, private facts, guest-specific claims, or one-off sensitive boundaries as general rules.

## Versions

Append a version after a formal generation or human return. Record parent version, stage, status, creator category, decision IDs, and output fingerprints. Media is referenced rather than copied into every version.

Do not silently rewrite history. A rollback selects an earlier version as the new parent; it does not delete later records.
