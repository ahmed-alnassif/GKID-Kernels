"""Offline fail-closed checks for pinned SUSFS patch preparation."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/prepare_susfs_kernel_patch.py"


class PrepareSusfsPatchTests(unittest.TestCase):
    def invoke(self, original, output):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(original), str(output)],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )

    def test_missing_input_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            original = Path(d) / "missing.patch"
            output = Path(d) / "result.patch"
            result = self.invoke(original, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BLOCKED:", result.stderr)
            self.assertFalse(output.exists())

    def test_wrong_sha_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            original = Path(d) / "original.patch"
            original.write_bytes(b"not the pinned SUSFS patch\n")
            output = Path(d) / "result.patch"
            result = self.invoke(original, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA256 mismatch", result.stderr)
            self.assertFalse(output.exists())

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            original = Path(d) / "original.patch"
            original.write_bytes(b"invalid input\n")
            output = Path(d) / "result.patch"
            output.write_bytes(b"keep this\n")
            result = self.invoke(original, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"keep this\n")

    def test_lock_still_requires_kernel_patch_only(self):
        lock = json.loads((ROOT / "configs/ksun-susfs-6.1.lock.json").read_text())
        self.assertEqual(lock["implementation"], "pershoot_builtin")
        self.assertFalse(lock["build_enabled"])
        self.assertTrue(lock["adaptation"]["includes_existing_namespace_fix"])


if __name__ == "__main__":
    unittest.main()
