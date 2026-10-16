#!/usr/bin/env python3
"""Offline regression tests for isolated KSUN+SUSFS patch replay."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "scripts" / "ksun_susfs_replay.py"


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.kernel = self.base / "kernel"
        self.kernel.mkdir()
        subprocess.run(["git", "init", "-q", str(self.kernel)], check=True)
        (self.kernel / "sample.txt").write_text("before\n")
        subprocess.run(["git", "-C", str(self.kernel), "add", "sample.txt"], check=True)
        subprocess.run(["git", "-C", str(self.kernel), "-c", "user.name=Test",
                        "-c", "user.email=test@example.invalid", "commit",
                        "-qm", "baseline"], check=True)
        self.patch = self.base / "change.patch"
        self.patch.write_text(
            "diff --git a/sample.txt b/sample.txt\n"
            "--- a/sample.txt\n+++ b/sample.txt\n"
            "@@ -1 +1 @@\n-before\n+after\n"
        )
        self.manifest = self.base / "manifest.json"
        self.write_manifest()

    def write_manifest(self, sha=None):
        head = subprocess.run(["git", "-C", str(self.kernel), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        self.manifest.write_text(json.dumps({"kernel_commit": head, "patches": [{
            "path": self.patch.name,
            "sha256": sha or hashlib.sha256(self.patch.read_bytes()).hexdigest()
        }]}))

    def run_replay(self, *args):
        return subprocess.run([sys.executable, str(REPLAY), str(self.kernel),
                               str(self.manifest), *args],
                              text=True, capture_output=True)

    def test_verify_only_does_not_modify_tree(self):
        result = self.run_replay()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.kernel / "sample.txt").read_text(), "before\n")

    def test_explicit_apply_changes_tree(self):
        result = self.run_replay("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.kernel / "sample.txt").read_text(), "after\n")

    def test_checksum_mismatch_blocks(self):
        self.write_manifest("0" * 64)
        result = self.run_replay("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.kernel / "sample.txt").read_text(), "before\n")

    def test_dirty_checkout_blocks(self):
        (self.kernel / "sample.txt").write_text("dirty\n")
        result = self.run_replay("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.kernel / "sample.txt").read_text(), "dirty\n")

    def test_wrong_kernel_commit_blocks(self):
        data = json.loads(self.manifest.read_text())
        data["kernel_commit"] = "0" * 40
        self.manifest.write_text(json.dumps(data))
        result = self.run_replay("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.kernel / "sample.txt").read_text(), "before\n")

    def test_kernel_commit_option_replaces_the_manifest_commit(self):
        head = json.loads(self.manifest.read_text())["kernel_commit"]
        data = json.loads(self.manifest.read_text())
        data["kernel_commit"] = "0" * 40  # another sublevel's commit
        self.manifest.write_text(json.dumps(data))
        result = self.run_replay("--apply", "--kernel-commit", head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.kernel / "sample.txt").read_text(), "after\n")

    def test_kernel_commit_option_must_match_head(self):
        for value in ("1" * 40, "HEAD", "abc"):
            result = self.run_replay("--apply", "--kernel-commit", value)
            self.assertNotEqual(result.returncode, 0, value)
            self.assertEqual((self.kernel / "sample.txt").read_text(), "before\n")

    def test_second_patch_failure_leaves_checkout_clean(self):
        second = self.base / "second.patch"
        second.write_text(
            "diff --git a/sample.txt b/sample.txt\\n"
            "--- a/sample.txt\\n+++ b/sample.txt\\n"
            "@@ -1 +1 @@\\n-missing\\n+broken\\n"
        )
        data = json.loads(self.manifest.read_text())
        data["patches"].append({
            "path": second.name,
            "sha256": hashlib.sha256(second.read_bytes()).hexdigest()
        })
        self.manifest.write_text(json.dumps(data))
        result = self.run_replay("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("preflight patch 2", result.stderr)
        self.assertEqual((self.kernel / "sample.txt").read_text(), "before\n")

    def test_nonapplicable_patch_blocks(self):
        self.patch.write_text(self.patch.read_text().replace("-before", "-absent"))
        self.write_manifest()
        result = self.run_replay("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.kernel / "sample.txt").read_text(), "before\n")


if __name__ == "__main__":
    unittest.main()
