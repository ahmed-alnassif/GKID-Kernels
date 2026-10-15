#!/usr/bin/env python3
"""Offline regression tests for the read-only KSUN+SUSFS preflight."""
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ksun_susfs_preflight.py"
spec = importlib.util.spec_from_file_location("ksun_susfs_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def test_lock_consistency_rejects_changed_pin(self):
        evidence = json.loads(preflight.EVIDENCE.read_text())
        lock = json.loads(preflight.LOCK.read_text())
        self.assertEqual(preflight.lock_consistency(lock, evidence), [])
        lock["sources"]["ksun"]["commit"] = "0" * 40
        self.assertIn("ksun lock/evidence commit mismatch",
                      preflight.lock_consistency(lock, evidence))

    def test_git_worktree_status_detects_local_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            tracked = root / "tracked.txt"
            tracked.write_text("original\\n")
            subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Test",
                            "-c", "user.email=test@example.invalid", "commit",
                            "-qm", "init"], check=True)
            self.assertEqual(preflight.git_worktree_status(root), "")
            tracked.write_text("modified\\n")
            self.assertTrue(preflight.git_worktree_status(root))

    def test_rejects_plain_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                preflight.git_head(Path(tmp))

    def test_rejects_nested_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            nested = root / "nested"
            nested.mkdir()
            with self.assertRaises(ValueError):
                preflight.git_head(nested)

    def test_accepts_git_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "main"
            worktree = Path(tmp) / "linked"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Test",
                            "-c", "user.email=test@example.invalid", "commit",
                            "--allow-empty", "-qm", "init"], check=True)
            subprocess.run(["git", "-C", str(root), "worktree", "add", "-q",
                            "-b", "candidate", str(worktree)], check=True)
            self.assertEqual(preflight.git_head(worktree), preflight.git_head(root))

    def test_missing_candidate_blocks_without_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = preflight.main(["preflight", str(root / "kernel"),
                                         str(root / "out"), str(root / "ksun"),
                                         str(root / "susfs")])
            self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
