# Audio evidence and subtitle rules

## Evidence hierarchy

1. Full audio determines wording, speaker, pause, overlap, and audible boundary.
2. Original SRT anchors evidence to the source timeline.
3. User terminology resolves spelling only when consistent with audio.
4. Context identifies a re-listen target but cannot fill inaudible speech.

## Evidence log

Use `templates/audio-text-check.csv`. `evidence_status` is one of:

- `verified`: wording and interval checked against audio;
- `reviewed`: checked and resolved through human review;
- `uncertain`: checked but a token remains explicitly uncertain;
- `overlap`: checked but overlapping speakers prevent a single clean reading;
- `pending`: not yet checked.

The first four statuses count as checked coverage. `uncertain` and `overlap` also enter the unresolved list. Coverage measures work performed, not correctness probability.

## Correction and segmentation

- Fix recognition errors, duplicated fragments, punctuation, and proper-name spelling only when audio supports the change.
- Preserve hedges and attribution such as “我觉得”, “可能”, “听说”, and “有人跟我说”.
- Preserve meaningful repetition, hesitation, dialect, and emotion in the complete corrected transcript.
- Use explicit markers such as `[听不清]`, `[人名待核]`, or `[多人同时说话]`; never guess.
- Prefer one semantic unit per cue and one displayed line up to 25 visible characters.
- Merge adjacent fragments with the first start and last end. Do not merge across speakers or meaningful pauses.
- Split inside a cue only after locating the boundary in audio. Never divide time proportionally by character count.
- Keep the complete corrected SRT free of editorial deletions.

## Required outputs

- complete corrected SRT on the source timeline;
- source-cue trace;
- audio-text evidence CSV;
- unresolved-items CSV;
- integrity report with duration, union coverage, status, and unresolved count.
