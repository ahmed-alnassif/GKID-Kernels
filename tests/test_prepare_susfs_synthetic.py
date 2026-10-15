"""Offline success-path regression for the SUSFS patch-of-patch preparer.

Uses a tiny synthetic patch fixture, never the real kernel or GitLab source.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


class SyntheticPreparationTests(unittest.TestCase):
    def test_successful_adjustment_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "scripts").mkdir()
            (base / "configs").mkdir()
            (base / "kernel-patches/susfs").mkdir(parents=True)
            shutil.copyfile(ROOT / "scripts/prepare_susfs_kernel_patch.py",
                            base / "scripts/prepare_susfs_kernel_patch.py")
            relative = "kernel_patches/50_add_susfs_in_gki-android14-6.1.patch"
            original = b"original patch contents\n"
            adjusted = b"adjusted patch contents\n"
            delta = (
                "diff --git a/" + relative + " b/" + relative + "\n"
                "--- a/" + relative + "\n"
                "+++ b/" + relative + "\n"
                "@@ -1 +1 @@\n"
                "-original patch contents\n"
                "+adjusted patch contents\n"
            ).encode()
            delta_path = base / "kernel-patches/susfs/companion.patch"
            delta_path.write_bytes(delta)
            lock = {
                "adaptation": {
                    "delta": "kernel-patches/susfs/companion.patch",
                    "applies_to": relative,
                    "input_sha256": sha(original),
                    "delta_sha256": sha(delta),
                    "output_sha256": sha(adjusted),
                }
            }
            (base / "configs/ksun-susfs-6.1.lock.json").write_text(json.dumps(lock))
            input_path = base / "original.patch"
            output_path = base / "adjusted.patch"
            input_path.write_bytes(original)
            command = [sys.executable, str(base / "scripts/prepare_susfs_kernel_patch.py"),
                       str(input_path), str(output_path)]
            first = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(output_path.read_bytes(), adjusted)
            second = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output_path.read_bytes(), adjusted)


if __name__ == "__main__":
    unittest.main()
