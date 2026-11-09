from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_release.py"
SPEC = importlib.util.spec_from_file_location("podcast_release_v2", SCRIPT)
RELEASE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = RELEASE
SPEC.loader.exec_module(RELEASE)


class ReleaseCase(unittest.TestCase):
    def make_minimal(self, root: Path) -> None:
        for relative in RELEASE.REQUIRED:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("safe\n", encoding="utf-8")

    def test_video_and_private_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "skill"
            self.make_minimal(root)
            (root / "demo.mp4").write_bytes(b"video")
            private_path = "/" + "Users/example/private/file.srt\n"
            (root / "references" / "leak.md").write_text(private_path, encoding="utf-8")
            issues = RELEASE.scan(root)
            self.assertTrue(any(item.startswith("video_not_allowed:") for item in issues))
            self.assertTrue(any(item.startswith("private_absolute_path:") for item in issues))

    def test_only_synthetic_demo_audio_is_allowed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "skill"
            self.make_minimal(root)
            demo = root / "demo" / "synthetic-episode"
            demo.mkdir(parents=True)
            (demo / "sample.wav").write_bytes(b"synthetic")
            self.assertEqual([], RELEASE.scan(root))
            (root / "private.wav").write_bytes(b"private")
            self.assertIn("audio_outside_synthetic_demo:private.wav", RELEASE.scan(root))

    def test_package_excludes_cache_files(self):
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            root = temp / "skill"
            self.make_minimal(root)
            cache = root / "scripts" / "__pycache__"
            cache.mkdir()
            (cache / "secret.pyc").write_bytes(b"cache")
            output = temp / "skill.zip"
            RELEASE.package(root, output)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
            self.assertFalse(any("__pycache__" in name for name in names))


if __name__ == "__main__":
    unittest.main()
