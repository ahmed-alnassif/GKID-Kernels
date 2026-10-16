#!/usr/bin/env python3
"""Offline tests for release_notes.py: component versions in the Manual Release notes."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import release_notes as rn

ROOT = Path(__file__).resolve().parents[1]
LOCK = rn.read_values((ROOT / "configs/upstream.lock").read_text())
FEATURES_LOCK = json.loads((ROOT / "configs/ksun-susfs-6.1-features.lock.json").read_text())
REPO = "cogan17/Cogan"
SHA = "a" * 40

KSUN = {
    "BUILD_VARIANT": "6.1-KSUN", "LINUX_VERSION": "6.1.177", "KSU": "KSUN", "KSU_SUSFS": "false",
    "KERNEL_SOURCE_REPO": "ahmed-alnassif/GKID", "KERNEL_SOURCE_BRANCH": LOCK["KERNEL_COMMIT_6_1"],
    "ROOT_MANAGER_REPO": "KernelSU-Next/KernelSU-Next", "ROOT_MANAGER_REF": LOCK["KSUN_REF"],
    "ROOT_MANAGER_SHA": LOCK["KSUN_COMMIT"], "COMPILER_STRING": "Neutron clang 22.0.0git",
    "KERNEL_FEATURES": "BBRv3 (default, also bbr3), BBG, NoMount, Full LTO",
}
CANDIDATE = dict(KSUN, BUILD_VARIANT="6.1-KSUN-SUSFS", KSU_SUSFS="true", ROOT_MANAGER_REPO="pershoot/KernelSU-Next",
                 ROOT_MANAGER_REF="candidate-v2", ROOT_MANAGER_SHA="b" * 40, SUSFS_SHA="9" * 40,
                 KERNEL_FEATURES="SUSFS, BBRv3 (default, also bbr3), BBG, NoMount, Full LTO")


def section(env):
    return "\n".join(rn.variant_section(env, LOCK, FEATURES_LOCK, REPO))


class ReleaseNotesTests(unittest.TestCase):
    def test_ksun_build_lists_matching_manager_and_pins(self):
        text = section(KSUN)
        self.assertIn("### 6.1-KSUN — Linux 6.1.177", text)
        self.assertIn(f"Root: KernelSU-Next/KernelSU-Next {LOCK['KSUN_REF']} (`{LOCK['KSUN_COMMIT'][:8]}`)", text)
        self.assertIn(f"https://github.com/KernelSU-Next/KernelSU-Next/releases/download/{LOCK['KSUN_REF']}/"
                      f"{LOCK['KSUN_MANAGER_APK']}", text)
        self.assertIn(LOCK["KSUN_SPOOFED_APK"], text)
        self.assertIn(f"NoMount: {LOCK['NOMOUNT_REF']} (`{LOCK['NOMOUNT_COMMIT'][:8]}`)", text)
        self.assertIn(LOCK["NOMOUNT_MODULE_ZIP"], text)
        self.assertIn(f"BBG: `{LOCK['BBG_COMMIT'][:8]}`", text)
        self.assertIn(f"AnyKernel3: `{LOCK['ANYKERNEL_COMMIT'][:8]}`", text)
        self.assertIn(f"(rilis / release {LOCK['NEUTRON_RELEASE']})", text)
        self.assertNotIn("SUSFS:", text)
        self.assertNotIn("if enabled", text)

    def test_candidate_uses_its_own_bbg_nomount_and_susfs(self):
        text = section(CANDIDATE)
        bbg, nomount = rn.feature_commit(FEATURES_LOCK, "bbg"), rn.feature_commit(FEATURES_LOCK, "nomount")
        self.assertTrue(bbg and nomount)
        self.assertIn("(kandidat beku / frozen candidate)", text)
        self.assertIn("Root: pershoot/KernelSU-Next candidate-v2 (`bbbbbbbb`)", text)
        self.assertIn("fork pershoot menerima manager KSUN resmi", text)
        self.assertIn("SUSFS: `99999999`", text)
        self.assertIn(f"BBG: `{bbg[:8]}`", text)
        self.assertIn(f"`{nomount[:8]}`", text)
        if nomount != LOCK["NOMOUNT_COMMIT"]:
            self.assertNotIn(LOCK["NOMOUNT_MODULE_ZIP"], text)

    def test_ci_only_spoofed_manager_links_to_the_mirror(self):
        env = dict(KSUN, BUILD_VARIANT="6.1-BSU-SUSFS", KSU="BSU", KSU_SUSFS="true", SUSFS_SHA="9" * 40,
                   ROOT_MANAGER_REPO="Baka-SU/BakaSU", ROOT_MANAGER_REF=LOCK["BSU_COMMIT"],
                   ROOT_MANAGER_SHA=LOCK["BSU_COMMIT"], KERNEL_FEATURES="SUSFS, BBG, NoMount, Full LTO")
        text = section(env)
        self.assertIn(f"https://github.com/{REPO}/releases/download/cogan-mirror/{LOCK['BSU_SPOOFED_APK']}", text)
        self.assertIn(f"https://github.com/Baka-SU/BakaSU/releases/download/{LOCK['BSU_REF']}/"
                      f"{LOCK['BSU_MANAGER_APK']}", text)
        self.assertIn(f"Root: Baka-SU/BakaSU {LOCK['BSU_REF']} (`{LOCK['BSU_COMMIT'][:8]}`)", text)
        self.assertNotIn("BBRv3", text)

    def test_build_without_recorded_features_marks_optional_parts(self):
        env = dict(KSUN)
        del env["KERNEL_FEATURES"]
        text = section(env)
        self.assertNotIn("Fitur / features", text)
        self.assertIn("NoMount (bila aktif / if enabled)", text)
        self.assertIn("BBG (bila aktif / if enabled)", text)

    def test_features_decide_what_is_listed(self):
        text = section(dict(KSUN, KERNEL_FEATURES="Thin LTO"))
        self.assertNotIn("NoMount", text)
        self.assertNotIn("BBG", text)

    def test_vanilla_has_no_root_lines(self):
        env = {"BUILD_VARIANT": "6.1-Vanilla", "LINUX_VERSION": "6.1.177", "KSU": "no",
               "KERNEL_SOURCE_BRANCH": LOCK["KERNEL_COMMIT_6_1"], "KERNEL_FEATURES": "Full LTO"}
        text = section(env)
        self.assertNotIn("Root:", text)
        self.assertNotIn("Manager", text)

    def test_workflows_save_and_use_the_metadata(self):
        build = (ROOT / ".github/workflows/build.yml").read_text()
        release = (ROOT / ".github/workflows/manual-release.yml").read_text()
        self.assertIn("KERNEL_FEATURES=${{ env.KERNEL_FEATURES }}", build)
        self.assertIn("python3 scripts/release_notes.py --lock source-pins/upstream.lock", release)
        self.assertIn('contents/configs/$file?ref=$SOURCE_SHA', release)
        self.assertIn("persist-credentials: false", release)

    def test_unsafe_values_are_dropped(self):
        values = rn.read_values("# c\nA=ok 1.2\nB=`x`\nC=[link](http://x)\nD=\n")
        self.assertEqual(values, {"A": "ok 1.2"})

    def test_cli_writes_one_section_per_build_env(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for name, env in (("a", KSUN), ("b", CANDIDATE)):
                (directory / name).mkdir()
                (directory / name / f"build-env-{env['BUILD_VARIANT']}.txt").write_text(
                    "".join(f"{key}={value}\n" for key, value in env.items()))
            args = ["--lock", str(ROOT / "configs/upstream.lock"),
                    "--features-lock", str(ROOT / "configs/ksun-susfs-6.1-features.lock.json"),
                    "--source-sha", SHA, "--repo", REPO, "--env-dir", str(directory)]
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(rn.main(args), 0)
                self.assertEqual(rn.main(args[:-1] + [str(directory / "missing")]), 1)
                self.assertEqual(rn.main(args[:4] + ["--source-sha", "nothex"] + args[6:]), 1)
            text = out.getvalue()
            self.assertTrue(text.startswith("## Versi komponen / Component versions\n"))
            self.assertEqual(text.count("\n### "), 2)
            self.assertIn("@ `aaaaaaaa`", text)


if __name__ == "__main__":
    unittest.main()
