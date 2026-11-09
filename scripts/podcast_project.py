#!/usr/bin/env python3
"""Create and maintain traceable audio-and-SRT podcast editing projects."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


SCHEMA_VERSION = "2.0"
SKILL_VERSION = "2.0.0"
AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}
TEXT_EXTENSIONS = {".csv", ".json", ".jsonl", ".md", ".srt"}
VIDEO_EXTENSIONS = {
    ".3gp",
    ".avi",
    ".flv",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".webm",
    ".wmv",
}
PROJECT_LAYOUT = (
    "00_input",
    "01_evidence",
    "02_transcript",
    "03_story",
    "04_rough-cut",
    "05_human-review",
    "06_clips",
    "07_post",
    "history",
)
TEMPLATE_LAYOUT = {
    "00_input": ("episode-brief.md",),
    "01_evidence": ("audio-text-check.csv", "uncertain-items.csv"),
    "03_story": ("narrative-diagnosis.md", "rough-cut-decisions.csv"),
    "05_human-review": ("review-decisions.csv",),
    "06_clips": ("highlight-candidates.csv", "clip-plan.md", "broll-cues.csv"),
    "07_post": ("post-cues.csv", "context-review.md"),
}
CHECKED_EVIDENCE_STATUSES = {"verified", "reviewed", "uncertain", "overlap"}


class ProjectError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProjectError(f"Expected a JSON object: {path}")
    return data


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, item: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ProjectError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ProjectError(f"Expected an object at {path}:{line_number}")
            rows.append(value)
    return rows


def ensure_empty_destination(destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ProjectError(f"Destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)


def reject_video(path: Path) -> None:
    if path.suffix.lower() in VIDEO_EXTENSIONS:
        raise ProjectError(f"Video input is not supported: {path}")


def validate_input_path(path: Path, expected: str) -> None:
    if not path.is_file():
        raise ProjectError(f"Input file does not exist: {path}")
    reject_video(path)
    suffix = path.suffix.lower()
    if expected == "audio" and suffix not in AUDIO_EXTENSIONS:
        raise ProjectError(f"Unsupported audio extension {suffix or '<none>'}: {path}")
    if expected == "srt" and suffix != ".srt":
        raise ProjectError(f"Expected an SRT file: {path}")


def fingerprint(path: Path) -> dict[str, object]:
    size = path.stat().st_size
    digest = hashlib.sha256()
    chunk_size = 1024 * 1024
    if size <= chunk_size * 2:
        digest.update(path.read_bytes())
        method = "sha256-full"
    else:
        with path.open("rb") as handle:
            digest.update(handle.read(chunk_size))
            handle.seek(max(0, size - chunk_size))
            digest.update(handle.read(chunk_size))
        digest.update(str(size).encode("ascii"))
        method = "sha256-head-tail-size"
    return {"method": method, "value": digest.hexdigest(), "size": size}


def wav_duration_ms(path: Path) -> int | None:
    if path.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(path), "rb") as audio:
            rate = audio.getframerate()
            frames = audio.getnframes()
    except (OSError, wave.Error):
        return None
    return round(frames * 1000 / rate) if rate else None


def file_record(path: Path, *, stored_path: str | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "path": stored_path or str(path.resolve()),
        "fingerprint": fingerprint(path),
        "modified_ns": path.stat().st_mtime_ns,
    }
    duration = wav_duration_ms(path)
    if duration is not None:
        record["duration_ms"] = duration
    return record


def templates_root() -> Path:
    return Path(__file__).resolve().parent.parent / "templates"


def create_layout(destination: Path) -> None:
    root = templates_root()
    for relative in PROJECT_LAYOUT:
        (destination / relative).mkdir(parents=True, exist_ok=True)
    for folder, names in TEMPLATE_LAYOUT.items():
        for name in names:
            source = root / name
            if not source.is_file():
                raise ProjectError(f"Missing Skill template: {source}")
            shutil.copy2(source, destination / folder / name)
    for name in ("versions.jsonl", "decisions.jsonl", "migrations.jsonl"):
        (destination / "history" / name).touch()


def project_path(directory: str | Path) -> Path:
    root = Path(directory).expanduser().resolve()
    if not (root / "project.json").is_file():
        raise ProjectError(f"Not a V2 project: {root}")
    return root


def load_project(directory: str | Path) -> tuple[Path, dict[str, object]]:
    root = project_path(directory)
    project = read_json(root / "project.json")
    if project.get("schema_version") != SCHEMA_VERSION:
        raise ProjectError(
            f"Unsupported project schema: {project.get('schema_version')!r}; expected {SCHEMA_VERSION!r}"
        )
    return root, project


def save_project(root: Path, project: dict[str, object]) -> None:
    project["updated_utc"] = now_utc()
    write_json(root / "project.json", project)


def initialize_project(
    destination: Path,
    *,
    title: str,
    audio_path: Path | None,
    srt_path: Path | None,
    offset_ms: int,
    show_profile: Path | None,
) -> dict[str, object]:
    if audio_path is not None:
        validate_input_path(audio_path, "audio")
    if srt_path is not None:
        validate_input_path(srt_path, "srt")
    if show_profile is not None and not (show_profile / "show.json").is_file():
        raise ProjectError(f"Show profile is missing show.json: {show_profile}")
    ensure_empty_destination(destination)
    create_layout(destination)
    inputs: dict[str, object] = {"audio": None, "original_srt": None}
    if audio_path is not None:
        inputs["audio"] = file_record(audio_path)
    if srt_path is not None:
        stored = destination / "00_input" / "original.srt"
        shutil.copy2(srt_path, stored)
        inputs["original_srt"] = file_record(stored, stored_path="00_input/original.srt")
    ready = audio_path is not None and srt_path is not None
    created = now_utc()
    project: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "project_id": str(uuid.uuid4()),
        "title": title,
        "created_utc": created,
        "updated_utc": created,
        "status": "ready_for_evidence" if ready else "incomplete",
        "current_stage": "intake",
        "timeline": {"rule": "output = source + offset_ms", "offset_ms": offset_ms},
        "show_profile": str(show_profile.resolve()) if show_profile else None,
        "show_rules": [],
        "inputs": inputs,
        "gates": {
            "inputs_complete": ready,
            "audio_srt_coverage_percent": 0.0,
            "audio_srt_check": "not_started",
            "actual_retained_mapping": "not_started",
            "context_review": "not_started",
        },
        "artifacts": {},
        "active_decisions": [],
        "latest_version_id": None,
        "migration": None,
    }
    write_json(destination / "project.json", project)
    return project


def command_init(args: argparse.Namespace) -> int:
    destination = Path(args.directory).expanduser().resolve()
    audio = Path(args.audio).expanduser().resolve() if args.audio else None
    srt = Path(args.srt).expanduser().resolve() if args.srt else None
    show = Path(args.show_profile).expanduser().resolve() if args.show_profile else None
    project = initialize_project(
        destination,
        title=args.title,
        audio_path=audio,
        srt_path=srt,
        offset_ms=args.offset_ms,
        show_profile=show,
    )
    print(json.dumps({"project": str(destination), "project_id": project["project_id"]}, ensure_ascii=False))
    return 0


def command_init_show(args: argparse.Namespace) -> int:
    destination = Path(args.directory).expanduser().resolve()
    ensure_empty_destination(destination)
    created = now_utc()
    show = {
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "show_id": str(uuid.uuid4()),
        "name": args.name,
        "created_utc": created,
        "updated_utc": created,
        "latest_rule_version": 0,
    }
    write_json(destination / "show.json", show)
    (destination / "editing-rules.jsonl").touch()
    print(destination)
    return 0


def output_record(root: Path, value: str) -> dict[str, object]:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ProjectError(f"Snapshot outputs must be inside the project: {path}") from exc
    if not path.is_file():
        raise ProjectError(f"Snapshot output does not exist: {path}")
    reject_video(path)
    return {"path": str(relative), "fingerprint": fingerprint(path)}


def command_snapshot(args: argparse.Namespace) -> int:
    root, project = load_project(args.project)
    version_id = str(uuid.uuid4())
    outputs = [output_record(root, item) for item in args.output]
    item = {
        "version_id": version_id,
        "parent_version_id": project.get("latest_version_id"),
        "created_utc": now_utc(),
        "creator": args.creator,
        "stage": args.stage,
        "status": args.status,
        "decision_ids": args.decision_id,
        "outputs": outputs,
        "note": args.note,
    }
    append_jsonl(root / "history" / "versions.jsonl", item)
    project["latest_version_id"] = version_id
    project["current_stage"] = args.stage
    project["status"] = args.status
    artifacts = project.setdefault("artifacts", {})
    if isinstance(artifacts, dict):
        for output in outputs:
            artifacts[str(output["path"])] = version_id
    save_project(root, project)
    print(version_id)
    return 0


def all_decisions(root: Path) -> list[dict[str, object]]:
    return read_jsonl(root / "history" / "decisions.jsonl")


def decision_by_id(root: Path, decision_id: str) -> dict[str, object]:
    for item in all_decisions(root):
        if item.get("decision_id") == decision_id:
            return item
    raise ProjectError(f"Decision not found: {decision_id}")


def make_decision(args: argparse.Namespace, supersedes: str | None = None) -> dict[str, object]:
    return {
        "decision_id": str(uuid.uuid4()),
        "created_utc": now_utc(),
        "scope": "episode",
        "stage": args.stage,
        "object_type": args.object_type,
        "object_ref": args.object_ref,
        "action": args.action,
        "reviewer_status": args.reviewer_status,
        "reason": args.reason,
        "evidence": args.evidence,
        "confidence": args.confidence,
        "exact_quote": args.exact_quote,
        "supersedes": supersedes,
    }


def command_add_decision(args: argparse.Namespace) -> int:
    root, project = load_project(args.project)
    item = make_decision(args)
    append_jsonl(root / "history" / "decisions.jsonl", item)
    active = project.setdefault("active_decisions", [])
    if isinstance(active, list):
        active.append(item["decision_id"])
    save_project(root, project)
    print(item["decision_id"])
    return 0


def command_supersede_decision(args: argparse.Namespace) -> int:
    root, project = load_project(args.project)
    old = decision_by_id(root, args.old_decision_id)
    item = make_decision(args, supersedes=args.old_decision_id)
    append_jsonl(root / "history" / "decisions.jsonl", item)
    active = project.setdefault("active_decisions", [])
    if isinstance(active, list):
        active[:] = [value for value in active if value != old["decision_id"]]
        active.append(item["decision_id"])
    save_project(root, project)
    print(item["decision_id"])
    return 0


def command_list_decisions(args: argparse.Namespace) -> int:
    root, project = load_project(args.project)
    decisions = all_decisions(root)
    if args.active:
        active = set(project.get("active_decisions") or [])
        decisions = [item for item in decisions if item.get("decision_id") in active]
    print(json.dumps(decisions, ensure_ascii=False, indent=2))
    return 0


def command_promote_rule(args: argparse.Namespace) -> int:
    root, project = load_project(args.project)
    source = decision_by_id(root, args.decision_id)
    show_root = Path(args.show_profile).expanduser().resolve()
    show_path = show_root / "show.json"
    show = read_json(show_path)
    if show.get("schema_version") != SCHEMA_VERSION:
        raise ProjectError(f"Unsupported show schema: {show.get('schema_version')!r}")
    version = int(show.get("latest_rule_version") or 0) + 1
    rule = {
        "rule_id": str(uuid.uuid4()),
        "version": version,
        "created_utc": now_utc(),
        "confirmed_by": args.confirmed_by,
        "source_project_id": project["project_id"],
        "source_decision_id": source["decision_id"],
        "applies_to_show_id": show["show_id"],
        "object_type": source["object_type"],
        "action": source["action"],
        "reason": source["reason"],
        "supersedes_rule_id": args.supersedes_rule_id,
    }
    append_jsonl(show_root / "editing-rules.jsonl", rule)
    show["latest_rule_version"] = version
    show["updated_utc"] = now_utc()
    write_json(show_path, show)
    print(rule["rule_id"])
    return 0


def union_coverage(intervals: Iterable[tuple[int, int]], duration_ms: int) -> int:
    normalized = sorted((max(0, start), min(duration_ms, end)) for start, end in intervals if end > start)
    total = 0
    current_start: int | None = None
    current_end: int | None = None
    for start, end in normalized:
        if start >= duration_ms or end <= 0:
            continue
        if current_start is None:
            current_start, current_end = start, end
        elif start <= int(current_end):
            current_end = max(int(current_end), end)
        else:
            total += int(current_end) - current_start
            current_start, current_end = start, end
    if current_start is not None and current_end is not None:
        total += current_end - current_start
    return total


def evidence_intervals(path: Path) -> tuple[list[tuple[int, int]], int]:
    intervals: list[tuple[int, int]] = []
    unresolved = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"start_ms", "end_ms", "evidence_status"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ProjectError(f"Evidence CSV must contain: {', '.join(sorted(required))}")
        for row_number, row in enumerate(reader, 2):
            if not any((value or "").strip() for value in row.values()):
                continue
            try:
                start = int((row.get("start_ms") or "").strip())
                end = int((row.get("end_ms") or "").strip())
            except ValueError as exc:
                raise ProjectError(f"Invalid evidence interval at row {row_number}") from exc
            if start < 0 or end <= start:
                raise ProjectError(f"Invalid evidence interval at row {row_number}: {start}-{end}")
            status = (row.get("evidence_status") or "").strip().lower()
            if status in CHECKED_EVIDENCE_STATUSES:
                intervals.append((start, end))
                if status in {"uncertain", "overlap"}:
                    unresolved += 1
    return intervals, unresolved


def project_audio_duration(project: dict[str, object]) -> int | None:
    inputs = project.get("inputs")
    if not isinstance(inputs, dict):
        return None
    audio = inputs.get("audio")
    if not isinstance(audio, dict):
        return None
    value = audio.get("duration_ms")
    return int(value) if isinstance(value, int) and value > 0 else None


def command_coverage(args: argparse.Namespace) -> int:
    root, project = load_project(args.project)
    evidence = Path(args.evidence).expanduser()
    if not evidence.is_absolute():
        evidence = root / evidence
    if not evidence.is_file():
        raise ProjectError(f"Evidence CSV not found: {evidence}")
    duration = args.duration_ms or project_audio_duration(project)
    if not duration or duration <= 0:
        raise ProjectError("Audio duration is unknown; pass --duration-ms")
    intervals, unresolved = evidence_intervals(evidence)
    covered = union_coverage(intervals, duration)
    percent = round(covered * 100 / duration, 4)
    inputs = project.get("inputs")
    inputs_complete = isinstance(inputs, dict) and bool(inputs.get("audio")) and bool(inputs.get("original_srt"))
    status = "complete" if inputs_complete and covered >= duration else ("partial" if covered else "not_started")
    gates = project.setdefault("gates", {})
    if isinstance(gates, dict):
        gates["audio_srt_coverage_percent"] = percent
        gates["audio_srt_check"] = status
        gates["inputs_complete"] = inputs_complete
    report = {
        "duration_ms": duration,
        "covered_ms": covered,
        "coverage_percent": percent,
        "status": status,
        "unresolved_items": unresolved,
        "evidence_file": str(evidence.relative_to(root)) if evidence.is_relative_to(root) else str(evidence),
    }
    write_json(root / "01_evidence" / "integrity-report.json", report)
    save_project(root, project)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "complete" else 2


def command_import_v1(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser().resolve()
    manifest_path = source / "episode.json"
    if not manifest_path.is_file():
        raise ProjectError(f"V1 project is missing episode.json: {source}")
    old = read_json(manifest_path)
    destination = Path(args.destination).expanduser().resolve()
    project = initialize_project(
        destination,
        title=str(old.get("title") or args.title or source.name),
        audio_path=None,
        srt_path=None,
        offset_ms=int(old.get("offset_ms") or 0),
        show_profile=None,
    )
    legacy = destination / "legacy-v1"
    legacy.mkdir()
    copied: list[str] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.name == "episode.json":
            continue
        reject_video(path)
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        relative = path.relative_to(source)
        target = legacy / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(str(relative))
    shutil.copy2(manifest_path, legacy / "episode.json")
    copied.append("episode.json")
    migration = {
        "migration_id": str(uuid.uuid4()),
        "created_utc": now_utc(),
        "source_format": "podcast-editing-v1",
        "source_path": str(source),
        "source_manifest_fingerprint": fingerprint(manifest_path),
        "status": "unverified_import",
        "copied_text_artifacts": copied,
    }
    append_jsonl(destination / "history" / "migrations.jsonl", migration)
    project["migration"] = migration
    project["status"] = "unverified_import"
    save_project(destination, project)
    print(json.dumps({"project": str(destination), "copied": len(copied)}, ensure_ascii=False))
    return 0


def validate_project(root: Path, project: dict[str, object]) -> list[str]:
    issues: list[str] = []
    for relative in PROJECT_LAYOUT:
        if not (root / relative).is_dir():
            issues.append(f"missing_directory:{relative}")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in VIDEO_EXTENSIONS:
            issues.append(f"video_not_allowed:{path.relative_to(root)}")
        elif suffix not in AUDIO_EXTENSIONS | TEXT_EXTENSIONS:
            issues.append(f"unsupported_project_file:{path.relative_to(root)}")
    for name in ("versions.jsonl", "decisions.jsonl", "migrations.jsonl"):
        path = root / "history" / name
        if not path.is_file():
            issues.append(f"missing_file:history/{name}")
            continue
        try:
            read_jsonl(path)
        except ProjectError as exc:
            issues.append(f"invalid_jsonl:{exc}")
    inputs = project.get("inputs")
    if not isinstance(inputs, dict):
        issues.append("invalid_inputs")
    return issues


def command_validate(args: argparse.Namespace) -> int:
    root, project = load_project(args.project)
    issues = validate_project(root, project)
    print(json.dumps({"project": str(root), "valid": not issues, "issues": issues}, ensure_ascii=False, indent=2))
    return 1 if issues else 0


def add_decision_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stage", required=True)
    parser.add_argument("--object-type", required=True)
    parser.add_argument("--object-ref", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--reviewer-status", default="proposed")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--evidence", default="")
    parser.add_argument("--confidence", choices=("high", "medium", "low"), default="medium")
    parser.add_argument("--exact-quote", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a V2 episode project")
    init.add_argument("directory")
    init.add_argument("--title", required=True)
    init.add_argument("--audio")
    init.add_argument("--srt")
    init.add_argument("--offset-ms", type=int, default=0)
    init.add_argument("--show-profile")
    init.set_defaults(func=command_init)

    init_show = subparsers.add_parser("init-show", help="Create an isolated show profile")
    init_show.add_argument("directory")
    init_show.add_argument("--name", required=True)
    init_show.set_defaults(func=command_init_show)

    snapshot = subparsers.add_parser("snapshot", help="Append a traceable project version")
    snapshot.add_argument("project")
    snapshot.add_argument("--stage", required=True)
    snapshot.add_argument("--status", required=True)
    snapshot.add_argument("--creator", choices=("model", "tool", "human"), required=True)
    snapshot.add_argument("--output", action="append", default=[])
    snapshot.add_argument("--decision-id", action="append", default=[])
    snapshot.add_argument("--note", default="")
    snapshot.set_defaults(func=command_snapshot)

    add_decision = subparsers.add_parser("add-decision", help="Append an episode decision")
    add_decision.add_argument("project")
    add_decision_arguments(add_decision)
    add_decision.set_defaults(func=command_add_decision)

    supersede = subparsers.add_parser("supersede-decision", help="Replace a decision without erasing history")
    supersede.add_argument("project")
    supersede.add_argument("old_decision_id")
    add_decision_arguments(supersede)
    supersede.set_defaults(func=command_supersede_decision)

    list_decisions = subparsers.add_parser("list-decisions", help="Print project decisions")
    list_decisions.add_argument("project")
    list_decisions.add_argument("--active", action="store_true")
    list_decisions.set_defaults(func=command_list_decisions)

    promote = subparsers.add_parser("promote-rule", help="Explicitly promote an episode decision to a show rule")
    promote.add_argument("project")
    promote.add_argument("decision_id")
    promote.add_argument("show_profile")
    promote.add_argument("--confirmed-by", required=True)
    promote.add_argument("--supersedes-rule-id")
    promote.set_defaults(func=command_promote_rule)

    coverage = subparsers.add_parser("coverage", help="Measure audio-SRT evidence coverage")
    coverage.add_argument("project")
    coverage.add_argument("--evidence", default="01_evidence/audio-text-check.csv")
    coverage.add_argument("--duration-ms", type=int)
    coverage.set_defaults(func=command_coverage)

    import_v1 = subparsers.add_parser("import-v1", help="Import V1 text artifacts without changing the source")
    import_v1.add_argument("source")
    import_v1.add_argument("destination")
    import_v1.add_argument("--title")
    import_v1.set_defaults(func=command_import_v1)

    validate = subparsers.add_parser("validate", help="Validate a V2 project")
    validate.add_argument("project")
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, ProjectError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
