# 《约跑》 case validation

## Available evidence

The preserved case contains `约跑预告1至4剪辑执行方案.docx` and its generation source. It records four reviewed trailer directions, source-timeline ranges, exact hook wording, deletion ranges, rhythm notes, visual suggestions, content boundaries, and a final subtitle checklist.

The case directory does **not** contain the original episode audio or original SRT. Therefore this V1.0 validation can test structure and timecode-preserving mechanics, but it cannot honestly certify audio transcription accuracy.

## Behaviors carried into the skill

- Source timecodes stay intact so the editor can locate every segment in DaVinci.
- Reordered hooks are listed in explicit edit order and are not confused with chronological source order.
- Deletion reasons distinguish long setup, repetition, filler, uncertainty, speaker overlap, topic drift, and sensitive-context preservation.
- Proper nouns remain review items when audio is uncertain.
- Opinion and allegation clips retain source limitations such as “我觉得” and “有人向我抱怨”.
- Safety advice keeps conditions instead of inventing a universal quantity or rule.
- Large text and sound effects are added only after clip content is fixed.

## Regression fixture

`tests/fixtures/yaopao_excerpt.srt` is a compact mechanics fixture derived from the preserved case's published source ranges and hook wording. It is not presented as a replacement for the missing original SRT.

The automated tests verify:

1. valid SRT parsing and line-length checks;
2. exact signed offset application;
3. cue-level deletions with unchanged retained timestamps and text;
4. deletion-report and trace-map generation;
5. source-versus-retained comparison;
6. non-destructive line reflow;
7. rejection of offsets that would create negative timecodes.

## Manual case review

The four preserved trailer structures were checked against the templates:

- each opens with an exact source-timed hook;
- each distinguishes retained and deleted ranges;
- montage order is explicit;
- uncertainty and content-boundary notes are retained;
- post-production guidance is downstream of the edit decision.

Audio-level checks remain pending until the original audio and SRT are supplied together.
