# Workflow and stage gates

## Project states

`intake → evidence → transcript → story → rough_cut → human_review → highlights → post → context_review`

Each formal delivery appends a version record. A stage may be `not_started`, `in_progress`, `partial`, `complete`, or `blocked`. Context review uses `context_ready`, `needs_revision`, or `blocked`.

## Intake gate

A complete run needs full audio and original SRT from the same episode. Record the explicit timeline rule, speakers, terminology, must-keep content, sensitive boundaries, platform, and duration constraints. Reject video inputs.

An SRT-only project may receive text-only structure analysis, but it must remain `incomplete` and must not claim audio verification.

## Evidence gate

Check the entire audio against the SRT and log interval evidence. Coverage is the union of checked source intervals divided by total audio duration. Duplicate or overlapping evidence rows cannot increase coverage. Only 100% coverage allows `complete`; unresolved checked words remain tagged and listed for review.

## Rough-cut gate

Bind every diagnosis and deletion candidate to corrected source cues and timecodes. Apply only whole-cue `delete` decisions. Preserve `review` items. The rough cut remains on the source timeline and is always labeled as a suggestion.

## Human-return gate

Require the actual retained SRT plus a source-timeline relation, explicit offset, marker list, or mapping. If a ripple-timeline SRT cannot be mapped unambiguously, stop highlight allocation and request the missing mapping.

Append human decisions; do not overwrite prior records. A same-episode explicit human decision takes precedence over a show rule.

## Highlight gate

Use only actual retained content. A candidate pool may be prepared before counts are known, but final allocation waits for requested clip and trailer counts. Preserve qualifications and source attribution.

## Post and context gate

Generate B-roll, large-text, and sound cues only after content is approved. Context review covers SRT, audio evidence, mappings, decisions, and text cues. It does not accept or review video.
