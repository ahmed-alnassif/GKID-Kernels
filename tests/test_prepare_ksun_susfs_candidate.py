#!/usr/bin/env python3
"""Offline rejection and staging tests for the isolated candidate preparer."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("candidate", ROOT / "scripts/prepare_ksun_susfs_candidate.py")
CANDIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CANDIDATE)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True,
                          text=True, capture_output=True).stdout.strip()


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.kernel = self.base / "kernel"
        self.ksun = self.base / "ksun"
        for path in (self.kernel, self.ksun):
            path.mkdir()
            git(path, "init", "-q")
        for name, raw in {"sample.txt": "before\n", "drivers/Makefile": "# drivers\n",
                          "drivers/Kconfig": "# config\n", "fs/original": "fs\n",
                          "include/linux/original": "include\n"}.items():
            p = self.kernel / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(raw)
        (self.ksun / "kernel").mkdir()
        (self.ksun / "kernel/Kbuild").write_text("# source\n")
        for path in (self.kernel, self.ksun):
            git(path, "add", ".")
            git(path, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "commit", "-qm", "fixture")
        self.root = self.base / "tool"
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "configs").mkdir()
        for name in ("prepare_susfs_kernel_patch.py", "ksun_susfs_replay.py"):
            shutil.copyfile(ROOT / "scripts" / name, self.root / "scripts" / name)
        original = b"diff --git a/sample.txt b/sample.txt\n--- a/sample.txt\n+++ b/sample.txt\n@@ -1 +1 @@\n-before\n+after\n"
        prepared = original.replace(b"+after\n", b"+staged\n")
        delta = "".join(difflib.unified_diff(original.decode().splitlines(keepends=True),
                       prepared.decode().splitlines(keepends=True),
                       fromfile="a/input/original.patch", tofile="b/input/original.patch")).encode()
        (self.root / "delta.patch").write_bytes(delta)
        driver = b"diff --git a/drivers/Makefile b/drivers/Makefile\n--- a/drivers/Makefile\n+++ b/drivers/Makefile\n@@ -1 +1,2 @@\n # drivers\n+obj-$(CONFIG_KSU) += kernelsu/\n"
        driver += b"diff --git a/drivers/kernelsu b/drivers/kernelsu\nnew file mode 120000\n--- /dev/null\n+++ b/drivers/kernelsu\n@@ -0,0 +1 @@\n+../../ksun/kernel\n\\ No newline at end of file\n"
        (self.root / "driver.patch").write_bytes(driver)
        self.raw = {"original.patch": original, "susfs.c": b"core\n",
                    "susfs.h": b"header\n", "susfs_def.h": b"defs\n"}
        self.lock = {
            "kernel_commit": git(self.kernel, "rev-parse", "HEAD"),
            "ksun_commit": git(self.ksun, "rev-parse", "HEAD"),
            "original_patch": "original.patch",
            "driver_integration": {"path": "driver.patch", "sha256": sha(driver)},
            "adaptation": {"delta": "delta.patch", "delta_sha256": sha(delta),
                           "applies_to": "input/original.patch", "input_sha256": sha(original),
                           "output_sha256": sha(prepared)},
            "files": [{"archive_path": name, "sha256": sha(raw),
                       **({"destination": {"susfs.c": "fs/susfs.c", "susfs.h": "include/linux/susfs.h",
                                             "susfs_def.h": "include/linux/susfs_def.h"}[name]} if name != "original.patch" else {})}
                      for name, raw in self.raw.items()],
        }
        (self.root / "configs/ksun-susfs-6.1.lock.json").write_text(json.dumps({"adaptation": self.lock["adaptation"]}))
        self.archive = self.base / "source.zip"
        self.write_zip()
        self.output = self.base / "bundle"

    def write_zip(self, extra=None, symlink=False):
        with zipfile.ZipFile(self.archive, "w") as z:
            for name, raw in self.raw.items():
                if symlink and name == "susfs.c":
                    item = zipfile.ZipInfo(name)
                    item.create_system = 3
                    item.external_attr = 0o120777 << 16
                    z.writestr(item, raw)
                else:
                    z.writestr(name, raw)
            if extra:
                z.writestr(extra, b"unexpected")

    def prepare(self, stage=False):
        with patch.object(CANDIDATE, "ROOT", self.root):
            CANDIDATE.write_bundle(self.archive, self.output, self.lock,
                                   self.kernel if stage else None,
                                   self.ksun if stage else None)

    def test_bundle_only_leaves_both_checkouts_clean(self):
        self.prepare()
        self.assertEqual(git(self.kernel, "status", "--porcelain"), "")
        self.assertEqual(git(self.ksun, "status", "--porcelain"), "")
        replay = json.loads((self.output / "kernel-replay.json").read_text())
        self.assertEqual(len(replay["patches"]), 2)
        self.assertEqual((self.output / "companions/fs/susfs.c").read_bytes(), b"core\n")

    def test_explicit_stage_replays_and_verifies_companions(self):
        self.prepare(stage=True)
        self.assertEqual((self.kernel / "sample.txt").read_text(), "staged\n")
        self.assertEqual((self.kernel / "drivers/kernelsu").resolve(), self.ksun / "kernel")
        self.assertEqual((self.kernel / "fs/susfs.c").read_bytes(), b"core\n")
        self.assertEqual(json.loads((self.output / "stage-evidence.json").read_text())["status"],
                         "source_staged_not_compilation_ready")

    def test_wrong_companion_bytes_block_before_output(self):
        self.raw["susfs.c"] = b"unreviewed replacement\n"
        self.write_zip()
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            self.prepare(stage=True)
        self.assertFalse(self.output.exists())
        self.assertEqual(git(self.kernel, "status", "--porcelain"), "")

    def test_unlisted_zip_path_is_rejected(self):
        self.write_zip(extra="../escaped.c")
        with self.assertRaisesRegex(ValueError, "exactly"):
            self.prepare()
        self.assertFalse((self.base / "escaped.c").exists())

    def test_zip_symlink_is_rejected(self):
        self.write_zip(symlink=True)
        with self.assertRaisesRegex(ValueError, "regular"):
            self.prepare()

    def test_changed_driver_patch_blocks_before_output(self):
        (self.root / "driver.patch").write_text("changed")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            self.prepare(stage=True)
        self.assertFalse(self.output.exists())

    def test_wrong_head_and_dirty_checkout_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "HEAD mismatch"):
            CANDIDATE.checkout(self.kernel, "0" * 40)
        (self.kernel / "sample.txt").write_text("dirty\n")
        with self.assertRaisesRegex(ValueError, "Dirty"):
            self.prepare(stage=True)
        self.assertFalse(self.output.exists())

    def test_existing_companion_or_output_is_not_overwritten(self):
        target = self.kernel / "fs/susfs.c"
        target.write_bytes(b"keep")
        git(self.kernel, "add", str(target))
        git(self.kernel, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "occupied")
        self.lock["kernel_commit"] = git(self.kernel, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "destination already exists"):
            self.prepare(stage=True)
        self.assertEqual(target.read_bytes(), b"keep")
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, "Output already exists"):
            self.prepare()

    def test_shallow_ksun_checkout_blocks_unshallow_side_effect(self):
        clone = self.base / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth=1", self.ksun.as_uri(), str(clone)], check=True)
        with self.assertRaisesRegex(ValueError, "Shallow KSUN"):
            CANDIDATE.checkout(clone, self.lock["ksun_commit"], nonshallow=True)

    def test_later_patch_rejection_keeps_kernel_clean_and_no_companion_copy(self):
        # Still a checksum-valid input; its kernel context is deliberately incompatible.
        old = self.lock["adaptation"]
        original = self.raw["original.patch"]
        prepared = original.replace(b"-before\n", b"-absent\n")
        delta = "".join(difflib.unified_diff(original.decode().splitlines(keepends=True),
                       prepared.decode().splitlines(keepends=True),
                       fromfile="a/input/original.patch", tofile="b/input/original.patch")).encode()
        (self.root / "delta.patch").write_bytes(delta)
        old.update(delta_sha256=sha(delta), output_sha256=sha(prepared))
        (self.root / "configs/ksun-susfs-6.1.lock.json").write_text(json.dumps({"adaptation": old}))
        with self.assertRaises(subprocess.CalledProcessError) as error:
            self.prepare(stage=True)
        self.assertIn("preflight patch 2", error.exception.stderr)
        self.assertEqual(git(self.kernel, "status", "--porcelain"), "")
        self.assertFalse((self.kernel / "fs/susfs.c").exists())


class LockedWorktreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tree = self.root / "tree"
        self.tree.mkdir()
        subprocess.run(["git", "init", "-q", str(self.tree)], check=True)
        (self.tree / "existing").write_bytes(b"before\n")
        subprocess.run(["git", "-C", str(self.tree), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.tree), "-c", "user.name=Test",
                        "-c", "user.email=test@example.invalid", "commit", "-qm", "base"], check=True)
        self.head = CANDIDATE.offline_git(self.tree, "rev-parse", "HEAD")

    def test_source_pin_and_cleanliness_are_required(self):
        self.assertEqual(CANDIDATE.verify_checkout(self.tree, self.head), self.tree)
        with self.assertRaisesRegex(ValueError, "HEAD mismatch"):
            CANDIDATE.verify_checkout(self.tree, "0" * 40)
        (self.tree / "unexpected").write_bytes(b"untracked\n")
        with self.assertRaisesRegex(ValueError, "dirty"):
            CANDIDATE.verify_checkout(self.tree, self.head)

    def test_reviewed_byte_change_is_rejected(self):
        raw = b"locked source\n"
        path = self.tree / "reviewed.c"
        path.write_bytes(raw)
        entries = {"reviewed.c": hashlib.sha256(raw).hexdigest()}
        self.assertEqual(CANDIDATE.verify_files(self.tree, entries)["reviewed.c"], raw)
        path.write_bytes(b"changed source\n")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            CANDIDATE.verify_files(self.tree, entries)

    def test_companion_symlink_is_rejected(self):
        external = self.root / "external.c"
        external.write_bytes(b"source\n")
        (self.tree / "companion.c").symlink_to(external)
        with self.assertRaisesRegex(ValueError, "escapes"):
            CANDIDATE.verify_files(self.tree, {"companion.c": CANDIDATE.digest(external.read_bytes())})

    def test_generated_patches_preserve_backslashes_and_blank_lines(self):
        raw = b"void init(void) {\\\n\n}\n"
        patch = CANDIDATE.text_patch("existing", "before\n", "after\n")
        patch += CANDIDATE.added_file_patch("fs/susfs.c", raw)
        subprocess.run(["git", "-C", str(self.tree), "apply", "--check", "-"], input=patch, check=True)
        subprocess.run(["git", "-C", str(self.tree), "apply", "-"], input=patch, check=True)
        self.assertEqual((self.tree / "existing").read_bytes(), b"after\n")
        self.assertEqual((self.tree / "fs/susfs.c").read_bytes(), raw)

    def test_non_text_or_unterminated_companion_is_rejected(self):
        for raw in (b"missing newline", b"binary\0\n"):
            with self.assertRaisesRegex(ValueError, "UTF-8"):
                CANDIDATE.added_file_patch("fs/susfs.c", raw)


if __name__ == "__main__":
    unittest.main()
