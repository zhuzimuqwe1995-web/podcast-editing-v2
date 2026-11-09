# V1 compatibility and import

Use `scripts/podcast_project.py import-v1 SOURCE DESTINATION`.

- Never import into the V1 directory.
- Copy only text artifacts and the old manifest into `legacy-v1/`; do not move or rename source files.
- Record the source path and manifest fingerprint in migration history.
- Mark imported material `unverified_import` until audio, original SRT, and mappings are confirmed.
- Do not invent a complete version history for files that predate V2.

V1 SRT mechanics remain regression requirements: parsing, signed offset, cue-level deletion with unchanged retained timecodes/text, deletion and trace reports, retained comparison, non-destructive reflow, and rejection of negative timecodes.

The preserved 《约跑》 fixture checks mechanics only. It does not contain the complete source audio and SRT, so it cannot certify transcription accuracy.
