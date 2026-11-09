from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "podcast_project.py"
SPEC = importlib.util.spec_from_file_location("podcast_project_v2", SCRIPT)
PROJECT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = PROJECT
SPEC.loader.exec_module(PROJECT)
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def make_wav(path: Path, duration_ms: int = 1000) -> None:
    rate = 8000
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\x00\x00" * round(rate * duration_ms / 1000))


def init_project(temp: Path, *, with_inputs: bool = True) -> Path:
    destination = temp / "episode"
    audio = temp / "source.wav"
    srt = FIXTURES / "yaopao_excerpt.srt"
    if with_inputs:
        make_wav(audio)
    PROJECT.initialize_project(
        destination,
        title="测试节目",
        audio_path=audio if with_inputs else None,
        srt_path=srt if with_inputs else None,
        offset_ms=0,
        show_profile=None,
    )
    return destination


class ProjectCase(unittest.TestCase):
    def test_init_creates_isolated_project_and_copies_srt(self):
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            project = init_project(temp)
            manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual("2.0", manifest["schema_version"])
            self.assertEqual("ready_for_evidence", manifest["status"])
            self.assertEqual(1000, manifest["inputs"]["audio"]["duration_ms"])
            self.assertTrue((project / "00_input" / "original.srt").is_file())
            self.assertTrue((project / "01_evidence" / "audio-text-check.csv").is_file())
            self.assertEqual([], PROJECT.validate_project(project, manifest))

    def test_video_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            video = temp / "episode.mp4"
            video.write_bytes(b"not-a-video")
            with self.assertRaises(PROJECT.ProjectError):
                PROJECT.validate_input_path(video, "audio")

    def test_project_validation_rejects_non_audio_non_text_files(self):
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            project = init_project(temp)
            (project / "00_input" / "attachment.pdf").write_bytes(b"pdf")
            manifest = PROJECT.read_json(project / "project.json")
            issues = PROJECT.validate_project(project, manifest)
            self.assertIn("unsupported_project_file:00_input/attachment.pdf", issues)

    def test_coverage_requires_full_union_not_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            project = init_project(temp)
            evidence = project / "01_evidence" / "audio-text-check.csv"
            with evidence.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "source_indexes",
                        "start_ms",
                        "end_ms",
                        "original_text",
                        "audio_observation",
                        "corrected_text",
                        "evidence_status",
                        "confidence",
                        "reviewer_resolution",
                    ],
                )
                writer.writeheader()
                writer.writerow({"start_ms": 0, "end_ms": 600, "evidence_status": "verified"})
                writer.writerow({"start_ms": 0, "end_ms": 600, "evidence_status": "verified"})
            partial = argparse.Namespace(project=str(project), evidence=str(evidence), duration_ms=1000)
            self.assertEqual(2, PROJECT.command_coverage(partial))
            report = json.loads((project / "01_evidence" / "integrity-report.json").read_text())
            self.assertEqual(60.0, report["coverage_percent"])
            with evidence.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["", 600, 1000, "", "", "", "uncertain", "low", ""])
            self.assertEqual(0, PROJECT.command_coverage(partial))
            report = json.loads((project / "01_evidence" / "integrity-report.json").read_text())
            self.assertEqual("complete", report["status"])
            self.assertEqual(1, report["unresolved_items"])

    def test_decision_history_supersedes_without_erasing(self):
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            project = init_project(temp)
            base = dict(
                project=str(project),
                stage="rough_cut",
                object_type="cue",
                object_ref="5",
                action="delete",
                reviewer_status="proposed",
                reason="重复",
                evidence="与第4条重复",
                confidence="medium",
                exact_quote="测试原话",
            )
            first_args = argparse.Namespace(**base)
            self.assertEqual(0, PROJECT.command_add_decision(first_args))
            root, manifest = PROJECT.load_project(project)
            first_id = manifest["active_decisions"][0]
            base.update(action="keep", reviewer_status="accepted", reason="人工决定保留")
            second_args = argparse.Namespace(old_decision_id=first_id, **base)
            self.assertEqual(0, PROJECT.command_supersede_decision(second_args))
            decisions = PROJECT.all_decisions(root)
            self.assertEqual(2, len(decisions))
            self.assertEqual(first_id, decisions[1]["supersedes"])
            manifest = PROJECT.read_json(root / "project.json")
            self.assertNotIn(first_id, manifest["active_decisions"])

    def test_promote_rule_requires_explicit_command_and_records_source(self):
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            project = init_project(temp)
            show = temp / "show"
            PROJECT.command_init_show(argparse.Namespace(directory=str(show), name="测试节目"))
            args = argparse.Namespace(
                project=str(project),
                stage="review",
                object_type="preference",
                object_ref="opening_length",
                action="keep_opening_short",
                reviewer_status="accepted",
                reason="用户确认",
                evidence="本期审核",
                confidence="high",
                exact_quote="",
            )
            PROJECT.command_add_decision(args)
            decision_id = PROJECT.read_json(project / "project.json")["active_decisions"][0]
            rules_path = show / "editing-rules.jsonl"
            self.assertEqual([], PROJECT.read_jsonl(rules_path))
            promote = argparse.Namespace(
                project=str(project),
                decision_id=decision_id,
                show_profile=str(show),
                confirmed_by="user",
                supersedes_rule_id=None,
            )
            PROJECT.command_promote_rule(promote)
            rules = PROJECT.read_jsonl(rules_path)
            self.assertEqual(1, len(rules))
            self.assertEqual(decision_id, rules[0]["source_decision_id"])

    def test_import_v1_preserves_source_files(self):
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            source = temp / "v1"
            source.mkdir()
            (source / "episode.json").write_text(
                json.dumps({"title": "旧项目", "offset_ms": 1250}, ensure_ascii=False), encoding="utf-8"
            )
            (source / "01.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n原话\n", encoding="utf-8")
            before = PROJECT.fingerprint(source / "01.srt")
            destination = temp / "v2"
            args = argparse.Namespace(source=str(source), destination=str(destination), title=None)
            self.assertEqual(0, PROJECT.command_import_v1(args))
            after = PROJECT.fingerprint(source / "01.srt")
            self.assertEqual(before, after)
            manifest = PROJECT.read_json(destination / "project.json")
            self.assertEqual("unverified_import", manifest["status"])
            self.assertTrue((destination / "legacy-v1" / "01.srt").is_file())


if __name__ == "__main__":
    unittest.main()
