#!/usr/bin/env python3
"""Offline tests for the KSUN + SUSFS sublevel table and its helper."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unittest import mock

from scripts import cogan_manual_update as mu
from scripts import gkid_parity as gp
from scripts import ksun_susfs_sublevel as ks

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "configs/ksun-susfs-6.1-features.lock.json").read_text())
UPSTREAM = mu.read_lock((ROOT / "configs/upstream.lock").read_text())
TOOL = ROOT / "scripts/ksun_susfs_sublevel.py"


class SublevelTableTests(unittest.TestCase):
    def test_device_tested_177_keeps_its_exact_identities(self):
        entry = LOCK["sublevels"]["177"]
        manifest = json.loads((ROOT / "kernel-patches/susfs/6.1-v2/replay/kernel-replay.json").read_text())
        self.assertEqual(entry["kernel_commit"], manifest["kernel_commit"])
        self.assertEqual(entry["core_kernel_tree"], LOCK["core_kernel_tree"])
        self.assertEqual(entry["kernel_snapshot"], LOCK["frozen_core"]["kernel_snapshot"])
        self.assertEqual(entry["integrated_kernel_tree"], LOCK["integrated_kernel_tree"])
        features = json.loads((ROOT / "kernel-patches/susfs/6.1-v2/features/kernel-replay.json").read_text())
        self.assertEqual(features["kernel_commit"], entry["kernel_snapshot"])

    def test_every_sublevel_uses_the_pinned_kernel_commit(self):
        self.assertEqual(sorted(LOCK["sublevels"], key=int), [str(n) for n in range(167, 178)])
        for sublevel, entry in LOCK["sublevels"].items():
            self.assertEqual(entry["kernel_commit"], UPSTREAM[f"KERNEL_COMMIT_6_1_{sublevel}"], sublevel)
            self.assertEqual(set(entry), {"kernel_commit", "core_kernel_tree", "kernel_snapshot",
                                          "integrated_kernel_tree", "gkid_stack", "final_kernel_tree"})
            for key, value in entry.items():
                if key != "gkid_stack":
                    self.assertRegex(value, r"^[0-9a-f]{40}$")
            # Only the GKID tip carries the GKID stack; older pins get the GKID-equivalent one.
            self.assertIs(entry["gkid_stack"], sublevel == "177", sublevel)
            same = entry["final_kernel_tree"] == entry["integrated_kernel_tree"]
            self.assertIs(same, entry["gkid_stack"], sublevel)
        trees = [entry["integrated_kernel_tree"] for entry in LOCK["sublevels"].values()]
        self.assertEqual(len(set(trees)), len(trees))

    def test_resolve_maps_lts_to_the_newest_verified_sublevel(self):
        self.assertEqual(ks.resolve("lts", LOCK), "177")
        for value in ("LTS", "Auto", "", " lts "):
            self.assertEqual(ks.resolve(value, LOCK), "177", value)
        for value in ("167", "170", "177"):
            self.assertEqual(ks.resolve(value, LOCK), value)
        for value in ("166", "160", "178", "6.1.177", "0177", "abc"):
            with self.assertRaisesRegex(ValueError, "not verified"):
                ks.resolve(value, LOCK)

    def test_cli(self):
        def run(*args):
            return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)
        self.assertEqual(run("resolve", "lts").stdout.strip(), "177")
        rejected = run("resolve", "165")
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("use lts or one of: 167", rejected.stderr)
        self.assertEqual(run().returncode, 2)
        self.assertEqual(run("record", "only-one-argument").returncode, 2)

    def test_record_refuses_a_kernel_that_is_not_6_1(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "Makefile").write_text("VERSION = 6\nPATCHLEVEL = 6\nSUBLEVEL = 1\n")
            subprocess.run(["git", "-C", str(repo), "add", "Makefile"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=T", "-c", "user.email=t@example.invalid",
                            "commit", "-qm", "base"], check=True)
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                                  capture_output=True, text=True).stdout.strip()
            with self.assertRaisesRegex(ValueError, "not a 6.1 kernel"):
                ks.identities(repo, head, LOCK)
            with self.assertRaisesRegex(ValueError, "40-character"):
                ks.identities(repo, "HEAD", LOCK)

    def test_build_gives_plain_lts_sublevels_the_gkid_stack(self):
        build = (ROOT / "build.sh").read_text()
        self.assertIn('elif ! grep -qE "disagrees about version of symbol.*but ignore" kernel/module/version.c; then',
                      build)
        self.assertIn("GKID parity incomplete", build)
        stage = (ROOT / "scripts/stage_ksun_susfs_candidate.py").read_text()
        self.assertIn('expect("final tree", git(kernel, "write-tree"), target["final_kernel_tree"])', stage)

    def test_build_rejects_sources_that_are_not_android_common_kernels(self):
        build = (ROOT / "build.sh").read_text()
        self.assertIn('[ ! -d "$KSRC/include/trace/hooks" ]', build)
        self.assertIn('compgen -G "$KSRC/android/abi_gki_aarch64*"', build)


class GkidParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.repo, self.patches = base / "kernel", base / "patches"
        self.patches.mkdir()
        (self.repo / "kernel/module").mkdir(parents=True)
        (self.repo / "android").mkdir()
        (self.repo / "kernel/module/version.c").write_text("pr_warn(\"disagrees about version of symbol\");\n")
        (self.repo / "android/abi_gki_aarch64").write_text("symbols\n")
        (self.repo / "android/abi_gki_protected_exports_aarch64").write_text("protected\n")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=T", "-c", "user.email=t@example.invalid",
                        "commit", "-qm", "base"], check=True)
        (self.patches / "0003-force-load.patch").write_text(
            "diff --git a/kernel/module/version.c b/kernel/module/version.c\n"
            "--- a/kernel/module/version.c\n+++ b/kernel/module/version.c\n@@ -1 +1 @@\n"
            "-pr_warn(\"disagrees about version of symbol\");\n"
            "+pr_warn(\"disagrees about version of symbol, but ignore...\");\n")
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(gp, "PATCH_DIR", self.patches).start()

    def test_stack_detection(self):
        self.assertFalse(gp.has_stack((self.repo / "kernel/module/version.c").read_text()))
        self.assertTrue(gp.has_stack('pr_warn("%s: disagrees about version of symbol %s, but ignore...\\n")'))

    def test_apply_patches_and_drops_protected_exports(self):
        self.assertEqual(gp.apply(self.repo), ["android/abi_gki_protected_exports_aarch64"])
        self.assertTrue(gp.has_stack((self.repo / "kernel/module/version.c").read_text()))
        self.assertFalse((self.repo / "android/abi_gki_protected_exports_aarch64").exists())
        self.assertTrue((self.repo / "android/abi_gki_aarch64").exists())

    def test_cached_apply_leaves_the_work_tree_alone(self):
        gp.apply(self.repo, cached=True)
        self.assertTrue((self.repo / "android/abi_gki_protected_exports_aarch64").exists())
        listed = subprocess.run(["git", "-C", str(self.repo), "ls-files"], capture_output=True, text=True).stdout
        self.assertNotIn("protected_exports", listed)

    def test_a_patch_that_does_not_apply_stops_everything(self):
        (self.patches / "0004-broken.patch").write_text(
            "diff --git a/missing.c b/missing.c\n--- a/missing.c\n+++ b/missing.c\n@@ -1 +1 @@\n-a\n+b\n")
        with self.assertRaisesRegex(RuntimeError, "0004-broken.patch does not apply"):
            gp.apply(self.repo)
        self.assertTrue((self.repo / "android/abi_gki_protected_exports_aarch64").exists())

    def test_missing_protected_exports_is_an_error(self):
        subprocess.run(["git", "-C", str(self.repo), "rm", "-q", "android/abi_gki_protected_exports_aarch64"], check=True)
        with self.assertRaisesRegex(RuntimeError, "no android/\\*protected_exports\\* file"):
            gp.apply(self.repo)


if __name__ == "__main__":
    unittest.main()
