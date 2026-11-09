#!/usr/bin/env python3
"""Conservative SRT inspection and source-timeline editing helpers."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Sequence


TIME_RE = re.compile(
    r"^(?P<sh>\d{1,3}):(?P<sm>\d{2}):(?P<ss>\d{2})[,.](?P<sms>\d{3})\s*-->\s*"
    r"(?P<eh>\d{1,3}):(?P<em>\d{2}):(?P<es>\d{2})[,.](?P<ems>\d{3})$"
)
BREAK_CHARS = set("，。！？；：、,.!?;: ")
ACTION_MAP = {
    "delete": "delete",
    "删除": "delete",
    "keep": "keep",
    "保留": "keep",
    "review": "review",
    "复核": "review",
    "待复核": "review",
}


class SRTError(ValueError):
    pass


@dataclass(frozen=True)
class Cue:
    index: int
    start_ms: int
    end_ms: int
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    cue_index: int | None
    message: str


def timestamp_to_ms(hours: str, minutes: str, seconds: str, millis: str) -> int:
    h, m, s, ms = map(int, (hours, minutes, seconds, millis))
    if m >= 60 or s >= 60:
        raise SRTError(f"Invalid timestamp component: {h:02}:{m:02}:{s:02},{ms:03}")
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def format_timestamp(value_ms: int) -> str:
    if value_ms < 0:
        raise SRTError(f"Negative timestamp is not allowed: {value_ms} ms")
    hours, rem = divmod(value_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def parse_srt(content: str) -> list[Cue]:
    content = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not content:
        raise SRTError("SRT is empty")
    blocks = re.split(r"\n\s*\n", content)
    cues: list[Cue] = []
    for block_number, block in enumerate(blocks, 1):
        lines = block.split("\n")
        if len(lines) < 3:
            raise SRTError(f"Block {block_number} has fewer than 3 lines")
        try:
            index = int(lines[0].strip())
        except ValueError as exc:
            raise SRTError(f"Block {block_number} has a non-numeric index: {lines[0]!r}") from exc
        match = TIME_RE.match(lines[1].strip())
        if not match:
            raise SRTError(f"Cue {index} has an invalid timestamp line: {lines[1]!r}")
        groups = match.groupdict()
        start = timestamp_to_ms(groups["sh"], groups["sm"], groups["ss"], groups["sms"])
        end = timestamp_to_ms(groups["eh"], groups["em"], groups["es"], groups["ems"])
        text_lines = tuple(line.rstrip() for line in lines[2:])
        cues.append(Cue(index, start, end, text_lines))
    return cues


def read_srt(path: str | Path) -> list[Cue]:
    return parse_srt(Path(path).read_text(encoding="utf-8-sig"))


def serialize_srt(cues: Sequence[Cue], *, reindex: bool = False) -> str:
    blocks: list[str] = []
    for position, cue in enumerate(cues, 1):
        index = position if reindex else cue.index
        timestamp = f"{format_timestamp(cue.start_ms)} --> {format_timestamp(cue.end_ms)}"
        blocks.append("\n".join((str(index), timestamp, *cue.lines)))
    return "\n\n".join(blocks) + "\n"


def write_srt(path: str | Path, cues: Sequence[Cue], *, reindex: bool = False) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(serialize_srt(cues, reindex=reindex), encoding="utf-8")


def visible_length(text: str) -> int:
    return sum(1 for char in text if not char.isspace())


def logical_text(lines: Sequence[str]) -> str:
    result = ""
    for raw in lines:
        part = raw.strip()
        if not part:
            continue
        if result and result[-1].isascii() and result[-1].isalnum() and part[0].isascii() and part[0].isalnum():
            result += " "
        result += part
    return result


def wrap_text(text: str, max_chars: int) -> tuple[str, ...]:
    if max_chars < 1:
        raise SRTError("max_chars must be at least 1")
    remaining = text.strip()
    if not remaining:
        return ("",)
    output: list[str] = []
    while visible_length(remaining) > max_chars:
        visible = 0
        hard_position = 0
        break_position = 0
        for position, char in enumerate(remaining, 1):
            if not char.isspace():
                visible += 1
            if char in BREAK_CHARS:
                break_position = position
            if visible >= max_chars:
                hard_position = position
                break
        position = break_position if break_position > 0 else hard_position
        if position <= 0:
            position = len(remaining)
        line = remaining[:position].strip()
        if not line:
            position = hard_position or 1
            line = remaining[:position].strip()
        output.append(line)
        remaining = remaining[position:].strip()
    if remaining:
        output.append(remaining)
    return tuple(output)


def inspect_cues(cues: Sequence[Cue], max_chars: int = 25) -> list[Issue]:
    issues: list[Issue] = []
    counts = Counter(cue.index for cue in cues)
    for index, count in counts.items():
        if count > 1:
            issues.append(Issue("error", "duplicate_index", index, f"Index appears {count} times"))
    previous: Cue | None = None
    for cue in cues:
        if cue.start_ms >= cue.end_ms:
            issues.append(Issue("error", "invalid_duration", cue.index, "Start must be before end"))
        if not any(line.strip() for line in cue.lines):
            issues.append(Issue("error", "empty_text", cue.index, "Cue has no text"))
        for line_number, line in enumerate(cue.lines, 1):
            length = visible_length(line)
            if length > max_chars:
                issues.append(
                    Issue(
                        "warning",
                        "long_line",
                        cue.index,
                        f"Line {line_number} has {length} visible characters (limit {max_chars})",
                    )
                )
        if previous:
            if cue.start_ms < previous.start_ms:
                issues.append(Issue("error", "out_of_order", cue.index, "Cue starts before previous cue"))
            if cue.start_ms < previous.end_ms:
                issues.append(
                    Issue(
                        "warning",
                        "overlap",
                        cue.index,
                        f"Overlaps cue {previous.index} by {previous.end_ms - cue.start_ms} ms",
                    )
                )
        previous = cue
    return issues


def parse_source_indexes(value: str) -> set[int]:
    value = value.strip().replace("，", ";").replace(",", ";")
    if not value:
        raise SRTError("source_indexes is empty")
    output: set[int] = set()
    for part in value.split(";"):
        part = part.strip()
        if not part:
            continue
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if range_match:
            start, end = map(int, range_match.groups())
            if end < start:
                raise SRTError(f"Descending source index range is not allowed: {part}")
            output.update(range(start, end + 1))
        elif part.isdigit():
            output.add(int(part))
        else:
            raise SRTError(f"Invalid source index expression: {part!r}")
    if not output:
        raise SRTError("source_indexes did not contain any cue IDs")
    return output


def load_decisions(path: str | Path, valid_indexes: set[int]) -> dict[int, dict[str, str]]:
    decisions: dict[int, dict[str, str]] = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"action", "source_indexes", "reason"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise SRTError(f"Decision CSV must contain columns: {', '.join(sorted(required))}")
        for row_number, row in enumerate(reader, 2):
            raw_action = (row.get("action") or "").strip().lower()
            if not raw_action and not (row.get("source_indexes") or "").strip():
                continue
            action = ACTION_MAP.get(raw_action)
            if action is None:
                raise SRTError(f"Decision row {row_number} has unsupported action: {raw_action!r}")
            if action == "delete" and not (row.get("reason") or "").strip():
                raise SRTError(f"Decision row {row_number} deletes cues without a reason")
            indexes = parse_source_indexes(row.get("source_indexes") or "")
            missing = indexes - valid_indexes
            if missing:
                raise SRTError(f"Decision row {row_number} references missing cue IDs: {sorted(missing)}")
            normalized = {key: (value or "").strip() for key, value in row.items() if key is not None}
            normalized["action"] = action
            for index in indexes:
                if index in decisions and decisions[index]["action"] != action:
                    raise SRTError(f"Cue {index} receives conflicting decisions")
                decisions[index] = normalized
    return decisions


def write_csv(path: str | Path, fieldnames: Sequence[str], rows: Iterable[dict[str, object]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def apply_decisions(
    source_path: str | Path,
    decisions_path: str | Path,
    output_path: str | Path,
    deletion_report_path: str | Path,
    trace_map_path: str | Path,
) -> tuple[int, int]:
    source = read_srt(source_path)
    decisions = load_decisions(decisions_path, {cue.index for cue in source})
    kept: list[Cue] = []
    deletions: list[dict[str, object]] = []
    trace: list[dict[str, object]] = []
    for cue in source:
        decision = decisions.get(cue.index, {"action": "keep", "reason": "", "evidence": "", "confidence": ""})
        if decision["action"] == "delete":
            deletions.append(
                {
                    "action": "delete",
                    "source_indexes": cue.index,
                    "start": format_timestamp(cue.start_ms),
                    "end": format_timestamp(cue.end_ms),
                    "original_text": logical_text(cue.lines),
                    "reason": decision.get("reason", ""),
                    "evidence": decision.get("evidence", ""),
                    "confidence": decision.get("confidence", ""),
                    "reviewer_status": decision.get("reviewer_status", ""),
                    "reviewer_note": decision.get("reviewer_note", ""),
                }
            )
            continue
        new_index = len(kept) + 1
        kept.append(replace(cue, index=new_index))
        trace.append(
            {
                "new_index": new_index,
                "source_index": cue.index,
                "start": format_timestamp(cue.start_ms),
                "end": format_timestamp(cue.end_ms),
                "text": logical_text(cue.lines),
                "decision": decision["action"],
            }
        )
    write_srt(output_path, kept)
    write_csv(
        deletion_report_path,
        [
            "action",
            "source_indexes",
            "start",
            "end",
            "original_text",
            "reason",
            "evidence",
            "confidence",
            "reviewer_status",
            "reviewer_note",
        ],
        deletions,
    )
    write_csv(trace_map_path, ["new_index", "source_index", "start", "end", "text", "decision"], trace)
    return len(kept), len(deletions)


def normalized_text(cue: Cue) -> str:
    return re.sub(r"\s+", "", logical_text(cue.lines))


def compare_srts(
    source_path: str | Path,
    kept_path: str | Path,
    output_path: str | Path,
    kept_offset_ms: int = 0,
) -> Counter:
    source = read_srt(source_path)
    kept = read_srt(kept_path)
    by_interval: dict[tuple[int, int], list[int]] = defaultdict(list)
    for position, cue in enumerate(kept):
        by_interval[(cue.start_ms, cue.end_ms)].append(position)
    used: set[int] = set()
    rows: list[dict[str, object]] = []
    summary: Counter = Counter()
    for src in source:
        expected = (src.start_ms + kept_offset_ms, src.end_ms + kept_offset_ms)
        exact_positions = [position for position in by_interval.get(expected, []) if position not in used]
        if exact_positions:
            position = exact_positions[0]
            used.add(position)
            target = kept[position]
            status = "kept" if normalized_text(src) == normalized_text(target) else "modified"
            note = "Exact interval match" if status == "kept" else "Exact interval; text differs"
        else:
            overlaps = [
                (position, cue)
                for position, cue in enumerate(kept)
                if position not in used
                and min(expected[1], cue.end_ms) > max(expected[0], cue.start_ms)
            ]
            if overlaps:
                position, target = max(
                    overlaps,
                    key=lambda item: min(expected[1], item[1].end_ms) - max(expected[0], item[1].start_ms),
                )
                status = "ambiguous"
                note = "Overlapping cue exists but interval is not exact; review mapping"
            else:
                target = None
                status = "deleted"
                note = "No matching or overlapping retained cue"
        summary[status] += 1
        rows.append(
            {
                "status": status,
                "source_index": src.index,
                "source_start": format_timestamp(src.start_ms),
                "source_end": format_timestamp(src.end_ms),
                "source_text": logical_text(src.lines),
                "kept_index": target.index if target else "",
                "kept_start": format_timestamp(target.start_ms) if target else "",
                "kept_end": format_timestamp(target.end_ms) if target else "",
                "kept_text": logical_text(target.lines) if target else "",
                "note": note,
            }
        )
    for position, cue in enumerate(kept):
        if position in used:
            continue
        if any(row["kept_index"] == cue.index and row["status"] == "ambiguous" for row in rows):
            continue
        summary["extra"] += 1
        rows.append(
            {
                "status": "extra",
                "source_index": "",
                "source_start": "",
                "source_end": "",
                "source_text": "",
                "kept_index": cue.index,
                "kept_start": format_timestamp(cue.start_ms),
                "kept_end": format_timestamp(cue.end_ms),
                "kept_text": logical_text(cue.lines),
                "note": "Retained cue has no exact source interval match",
            }
        )
    write_csv(
        output_path,
        [
            "status",
            "source_index",
            "source_start",
            "source_end",
            "source_text",
            "kept_index",
            "kept_start",
            "kept_end",
            "kept_text",
            "note",
        ],
        rows,
    )
    return summary


def command_inspect(args: argparse.Namespace) -> int:
    cues = read_srt(args.input)
    issues = inspect_cues(cues, args.max_chars)
    report = {
        "file": str(Path(args.input).resolve()),
        "cue_count": len(cues),
        "first_start": format_timestamp(cues[0].start_ms),
        "last_end": format_timestamp(cues[-1].end_ms),
        "issues": [issue.__dict__ for issue in issues],
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Cues: {report['cue_count']}")
        print(f"Range: {report['first_start']} --> {report['last_end']}")
        if not issues:
            print("Issues: none")
        for issue in issues:
            cue = f" cue={issue.cue_index}" if issue.cue_index is not None else ""
            print(f"{issue.severity.upper()} {issue.code}{cue}: {issue.message}")
    has_error = any(issue.severity == "error" for issue in issues)
    has_warning = any(issue.severity == "warning" for issue in issues)
    return 1 if has_error or (args.fail_on_warning and has_warning) else 0


def command_reflow(args: argparse.Namespace) -> int:
    cues = read_srt(args.input)
    output = [replace(cue, lines=wrap_text(logical_text(cue.lines), args.max_chars)) for cue in cues]
    write_srt(args.output, output)
    return 0


def command_offset(args: argparse.Namespace) -> int:
    cues = read_srt(args.input)
    shifted: list[Cue] = []
    for cue in cues:
        start = cue.start_ms + args.milliseconds
        end = cue.end_ms + args.milliseconds
        if start < 0 or end < 0:
            raise SRTError(f"Offset would create a negative timestamp at cue {cue.index}")
        shifted.append(replace(cue, start_ms=start, end_ms=end))
    write_srt(args.output, shifted)
    return 0


def command_apply(args: argparse.Namespace) -> int:
    kept, deleted = apply_decisions(
        args.input,
        args.decisions,
        args.output,
        args.deletion_report,
        args.trace_map,
    )
    print(f"Kept cues: {kept}")
    print(f"Deleted cues: {deleted}")
    return 0


def command_compare(args: argparse.Namespace) -> int:
    summary = compare_srts(args.source, args.kept, args.output, args.kept_offset_ms)
    print(" ".join(f"{key}={summary[key]}" for key in sorted(summary)))
    return 2 if summary["ambiguous"] or summary["extra"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Validate structure, order, overlaps, and line length")
    inspect_parser.add_argument("input")
    inspect_parser.add_argument("--max-chars", type=int, default=25)
    inspect_parser.add_argument("--json", action="store_true")
    inspect_parser.add_argument("--fail-on-warning", action="store_true")
    inspect_parser.set_defaults(func=command_inspect)

    reflow_parser = subparsers.add_parser("reflow", help="Change line wrapping only")
    reflow_parser.add_argument("input")
    reflow_parser.add_argument("output")
    reflow_parser.add_argument("--max-chars", type=int, default=25)
    reflow_parser.set_defaults(func=command_reflow)

    offset_parser = subparsers.add_parser("offset", help="Apply an explicit signed millisecond offset")
    offset_parser.add_argument("input")
    offset_parser.add_argument("output")
    offset_parser.add_argument("--milliseconds", type=int, required=True)
    offset_parser.set_defaults(func=command_offset)

    apply_parser = subparsers.add_parser("apply", help="Apply conservative cue-level deletion decisions")
    apply_parser.add_argument("input")
    apply_parser.add_argument("decisions")
    apply_parser.add_argument("output")
    apply_parser.add_argument("--deletion-report", required=True)
    apply_parser.add_argument("--trace-map", required=True)
    apply_parser.set_defaults(func=command_apply)

    compare_parser = subparsers.add_parser("compare", help="Compare corrected source and actual retained SRT")
    compare_parser.add_argument("source")
    compare_parser.add_argument("kept")
    compare_parser.add_argument("output")
    compare_parser.add_argument(
        "--kept-offset-ms",
        type=int,
        default=0,
        help="Explicit relation: kept timestamps = source timestamps + this value",
    )
    compare_parser.set_defaults(func=command_compare)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, SRTError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
