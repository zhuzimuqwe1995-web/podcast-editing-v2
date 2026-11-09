#!/usr/bin/env python3
"""Validate and optionally package a public podcast-editing Skill release."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Sequence


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
AUDIO_EXTENSIONS = {".aac", ".aif", ".aiff", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".wma"}
TEXT_EXTENSIONS = {".csv", ".json", ".jsonl", ".md", ".py", ".srt", ".yaml", ".yml"}
REQUIRED = {
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/podcast_project.py",
    "scripts/srt_tool.py",
    "references/workflow.md",
    "references/schemas.md",
}
PRIVATE_PATH_PATTERNS = (
    re.compile("/" + r"Users/[^/\s]+/"),
    re.compile("/" + r"home/[^/\s]+/"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\"),
)


def ignored(path: Path) -> bool:
    return any(part in {"__pycache__", ".git", ".pytest_cache"} for part in path.parts) or path.name == ".DS_Store"


def scan(root: Path) -> list[str]:
    issues: list[str] = []
    for required in sorted(REQUIRED):
        if not (root / required).is_file():
            issues.append(f"missing_required:{required}")
    for path in sorted(root.rglob("*")):
        if ignored(path) or not path.is_file():
            continue
        relative = path.relative_to(root)
        suffix = path.suffix.lower()
        if suffix in VIDEO_EXTENSIONS:
            issues.append(f"video_not_allowed:{relative}")
        if suffix in AUDIO_EXTENSIONS and relative.parts[:2] != ("demo", "synthetic-episode"):
            issues.append(f"audio_outside_synthetic_demo:{relative}")
        if suffix in TEXT_EXTENSIONS:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                issues.append(f"non_utf8_text:{relative}")
                continue
            for pattern in PRIVATE_PATH_PATTERNS:
                if pattern.search(text):
                    issues.append(f"private_absolute_path:{relative}")
                    break
    return issues


def package(root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if ignored(path) or not path.is_file():
                continue
            archive.write(path, Path(root.name) / path.relative_to(root))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill")
    parser.add_argument("--zip-output")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.skill).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: Skill directory does not exist: {root}", file=sys.stderr)
        return 1
    issues = scan(root)
    result: dict[str, object] = {"skill": str(root), "valid": not issues, "issues": issues}
    if not issues and args.zip_output:
        output = Path(args.zip_output).expanduser().resolve()
        if output.exists() and not args.overwrite:
            print(f"ERROR: Zip output exists: {output}", file=sys.stderr)
            return 1
        package(root, output)
        result["zip"] = str(output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
