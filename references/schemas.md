# Project schemas

## `project.json`

Required top-level fields:

- `schema_version`, `skill_version`, `project_id`, `title`;
- `created_utc`, `updated_utc`, `status`, `current_stage`;
- `timeline` with explicit offset rule;
- `inputs` with audio and original-SRT records;
- `gates`, `artifacts`, `active_decisions`, `latest_version_id`;
- optional `show_profile`, `show_rules`, and `migration`.

Input records contain a path, size/fingerprint, modification time, and duration when available. Large audio uses a head-tail-size fingerprint; SRT and small files use full SHA-256.

## JSONL histories

`versions.jsonl` is append-only and records version ID, parent, stage, status, creator, decision IDs, outputs, fingerprints, and note.

`decisions.jsonl` is append-only and records decision ID, scope, stage, object, action, reviewer status, reason, evidence, confidence, exact quote, and optional `supersedes`.

`migrations.jsonl` records source format/path, source manifest fingerprint, import status, and copied text artifacts.

`editing-rules.jsonl` belongs to a show profile and records rule ID/version, explicit confirmer, source project/decision, target show, action, reason, and optional replaced rule.

## CSV status vocabularies

- evidence: `verified`, `reviewed`, `uncertain`, `overlap`, `pending`;
- rough cut: `keep`, `delete`, `review`;
- reviewer: `proposed`, `accepted`, `rejected`, `adjusted`;
- confidence: `high`, `medium`, `low`;
- context review: `context_ready`, `needs_revision`, `blocked`.

All source references use original cue IDs or explicit source intervals. Reordered output preserves source segment order in a separate mapping.
