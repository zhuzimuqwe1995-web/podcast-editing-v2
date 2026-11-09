---
name: podcast-editing-v2
description: Process long-form Chinese podcasts from full audio and SRT inputs only. Use for audio-verified transcript correction, source-timecode rough cuts, narrative diagnosis, human edit-decision memory, retained-program highlight planning, B-roll or post-production text cues, and context review. Do not use for video input, video review, invented dialogue, or replacing the human DaVinci edit.
metadata:
  version: "2.0.0"
---

# Podcast Editing V2

Create reviewable podcast-editing artifacts from full audio and SRT while keeping every wording and edit decision traceable to the source recording.

## Input boundary

Accept audio, SRT, and supporting CSV/JSON/JSONL/Markdown only. Reject video files. B-roll, large-text, and sound suggestions are text plans derived from the approved transcript; they are not video analysis.

For a new project, use `scripts/podcast_project.py init`. For an old V1 episode directory, use `import-v1`; never migrate it in place. Read [references/workflow.md](references/workflow.md) for stage gates and [references/schemas.md](references/schemas.md) when creating or validating structured files.

## Non-negotiable invariants

- Audio determines what was said. The original SRT supplies source-timeline evidence. Context identifies where to re-listen; it cannot invent a word.
- Preserve meaning, uncertainty, attribution, qualification, and tone. Never convert opinion, hearsay, or uncertainty into fact.
- Keep deliverables on the source timeline unless an explicit relation is recorded. Never infer a ripple-timeline mapping silently.
- A suggested deletion is not an executed edit. Mechanical rough cuts remove only whole verified cues. Cue-internal cuts require an audio boundary or human review.
- Project decisions stay inside the episode unless the user explicitly promotes a reusable preference to an isolated show profile.
- Formal clip/trailer allocation uses the actual retained SRT, not the AI rough cut.
- A context review checks audio, SRT, mappings, decisions, and text suggestions only. It does not certify any video or editing project.

## Route by current stage

### 1. Intake and project integrity

Require the full audio and original SRT for a complete run. Record speakers, terminology, offset, target platforms, must-keep content, and sensitive boundaries. Run `srt_tool.py inspect` and validate the project. If either primary input is missing, save an incomplete project and state which claims cannot be made.

### 2. Audio—SRT evidence and corrected transcript

Read [references/evidence-and-subtitles.md](references/evidence-and-subtitles.md). Log checked intervals in `audio-text-check.csv`, unresolved words in `uncertain-items.csv`, and produce a complete corrected SRT plus source trace. Only mark this stage complete when checked interval union covers 100% of the audio. Uncertain or overlapping speech may remain explicitly tagged after it has been checked.

### 3. Narrative diagnosis and suggested rough cut

Read [references/narrative-and-rough-cut.md](references/narrative-and-rough-cut.md). Diagnose structure from the corrected transcript, create `keep`/`delete`/`review` decisions, then use `srt_tool.py apply` for conservative whole-cue deletion. Deliver the corrected SRT, source-timeline rough cut, deletion table, trace map, narrative diagnosis, and DaVinci review questions together.

### 4. Human edit return and decision memory

Wait for the actual retained SRT and an explicit timeline relation or mapping. Compare it with the corrected source, resolve ambiguous mappings with the user, and append accepted/rejected/adjusted decisions. Read [references/decisions-and-versioning.md](references/decisions-and-versioning.md). Do not erase superseded decisions or promote a rule across episodes without explicit confirmation.

### 5. Highlights, clips, trailers, and post text cues

Read [references/highlights-and-post.md](references/highlights-and-post.md). Generate a candidate pool only from retained content. If final clip and trailer counts are missing, ask once before allocation; candidates may still be prepared. Quote exact words with source timecodes, preserve required qualifications, and distinguish continuous excerpts from reordered montage.

After content is approved, produce B-roll, large-text, and sound-effect suggestions as text tables. Do not describe suggested visuals as existing or verified footage.

### 6. Context review

Read [references/context-review.md](references/context-review.md). Review final retained SRT, source mapping, decisions, and post text cues. Return `context_ready`, `needs_revision`, or `blocked`, with exact evidence and required action. Never claim to have reviewed video, subtitle burn-in, lip sync, or an editing project.

## Deterministic tools

- `scripts/podcast_project.py`: initialize and validate projects, measure evidence coverage, append versions and decisions, promote show rules, and import V1 projects.
- `scripts/srt_tool.py`: inspect, reflow, offset, apply cue-level decisions, and compare retained SRT against corrected source.
- `scripts/validate_release.py`: block videos, private paths, and non-demo media from a public package, then optionally build a zip.

Read [references/migration-v1.md](references/migration-v1.md) for V1 import or compatibility work. Read [references/case-yaopao.md](references/case-yaopao.md) only when checking the preserved mechanics fixture.
