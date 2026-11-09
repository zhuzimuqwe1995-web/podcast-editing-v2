#!/usr/bin/env python3
"""Compatibility wrapper that creates an incomplete V2 episode project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from podcast_project import ProjectError, initialize_project


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--title", required=True)
    parser.add_argument("--offset-ms", type=int, default=0)
    args = parser.parse_args()
    destination = Path(args.directory).expanduser().resolve()
    try:
        initialize_project(
            destination,
            title=args.title,
            audio_path=None,
            srt_path=None,
            offset_ms=args.offset_ms,
            show_profile=None,
        )
    except (OSError, ProjectError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
