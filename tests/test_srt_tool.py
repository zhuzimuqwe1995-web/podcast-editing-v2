from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "srt_tool.py"
SPEC = importlib.util.spec_from_file_location("podcast_srt_tool", SCRIPT)
TOOL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = TOOL
SPEC.loader.exec_module(TOOL)
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class SRTToolCase(unittest.TestCase):
    def test_case_fixture_is_valid(self):
        cues = TOOL.read_srt(FIXTURES / "yaopao_excerpt.srt")
        self.assertEqual(12, len(cues))
        self.assertEqual([], TOOL.inspect_cues(cues, 25))

    def test_offset_preserves_text_and_duration(self):
        cues = TOOL.read_srt(FIXTURES / "yaopao_excerpt.srt")
        shifted = [TOOL.replace(cue, start_ms=cue.start_ms + 1250, end_ms=cue.end_ms + 1250) for cue in cues]
        for original, output in zip(cues, shifted):
            self.assertEqual(original.lines, output.lines)
            self.assertEqual(original.end_ms - original.start_ms, output.end_ms - output.start_ms)
            self.assertEqual(1250, output.start_ms - original.start_ms)

    def test_negative_timestamp_is_rejected(self):
        cue = TOOL.Cue(1, 500, 900, ("测试",))
        with self.assertRaises(TOOL.SRTError):
            TOOL.format_timestamp(cue.start_ms - 1000)

    def test_reflow_preserves_logical_text(self):
        source = "这是一个用于验证换行但不改写原话的很长字幕句子"
        lines = TOOL.wrap_text(source, 10)
        self.assertEqual(source, TOOL.logical_text(lines))
        self.assertTrue(all(TOOL.visible_length(line) <= 10 for line in lines))

    def test_apply_preserves_retained_source_timestamps_and_text(self):
        source_path = FIXTURES / "yaopao_excerpt.srt"
        decisions_path = FIXTURES / "yaopao_decisions.csv"
        source = TOOL.read_srt(source_path)
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            output = temp_path / "rough.srt"
            report = temp_path / "deletions.csv"
            trace = temp_path / "trace.csv"
            kept_count, deleted_count = TOOL.apply_decisions(
                source_path, decisions_path, output, report, trace
            )
            self.assertEqual(10, kept_count)
            self.assertEqual(2, deleted_count)
            kept = TOOL.read_srt(output)
            expected = source[2:]
            for actual, original in zip(kept, expected):
                self.assertEqual(original.start_ms, actual.start_ms)
                self.assertEqual(original.end_ms, actual.end_ms)
                self.assertEqual(original.lines, actual.lines)
            with report.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(["1", "2"], [row["source_indexes"] for row in rows])
            with trace.open("r", encoding="utf-8-sig", newline="") as handle:
                trace_rows = list(csv.DictReader(handle))
            review_row = next(row for row in trace_rows if row["source_index"] == "5")
            self.assertEqual("review", review_row["decision"])

    def test_compare_reports_deleted_without_ambiguity(self):
        source_path = FIXTURES / "yaopao_excerpt.srt"
        decisions_path = FIXTURES / "yaopao_decisions.csv"
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            rough = temp_path / "rough.srt"
            TOOL.apply_decisions(
                source_path,
                decisions_path,
                rough,
                temp_path / "deletions.csv",
                temp_path / "trace.csv",
            )
            summary = TOOL.compare_srts(source_path, rough, temp_path / "compare.csv")
            self.assertEqual(2, summary["deleted"])
            self.assertEqual(10, summary["kept"])
            self.assertEqual(0, summary["ambiguous"])
            self.assertEqual(0, summary["extra"])


if __name__ == "__main__":
    unittest.main()
