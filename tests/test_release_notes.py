#!/usr/bin/env python3
"""Offline tests for release_notes.py: component versions in the Manual Release notes."""
import contextlib
import io
import json
import tempfile
import unittest
import zipfile
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

    def test_rothko_build_names_its_device(self):
        self.assertIn("Perangkat / device: Xiaomi 14T Pro (rothko)", section(dict(CANDIDATE, TARGET_DEVICE="rothko")))
        self.assertNotIn("Perangkat / device", section(dict(CANDIDATE, TARGET_DEVICE="generic")))
        self.assertNotIn("Perangkat / device", section(CANDIDATE))  # build-env written before the option

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

    def test_release_files_table_matches_the_build_downloads(self):
        names = ["checksums.txt", "4-NOMOUNT-MODULE_v2.1.1.zip", "2-MANAGER_KernelSU-Next_v3.4.2.apk",
                 "1-KERNEL_Cogan-6.1.177_KernelSU-Next+SuSFS_v26.10.16-r3.zip",
                 "3-MANAGER-SPOOFED_KernelSU-Next_v3.4.2.apk", "unexpected.bin"]
        table = rn.files_section(names)
        self.assertEqual(table[0], "## Isi rilis / Release files")
        rows = [row for row in table if row.startswith("| `")]
        self.assertEqual([row.split("`")[1] for row in rows], sorted(n for n in names if n != "unexpected.bin"))
        self.assertIn("Kernel Flasher", rows[0])
        self.assertIn("pilih 2 **atau** 3", rows[1])
        self.assertIn("pilih 2 **atau** 3", rows[2])
        self.assertNotIn("pilih 2", rows[3])
        self.assertNotIn("pilih 2", "\n".join(rn.files_section(["2-MANAGER_KernelSU_v3.3.1.apk"])))
        self.assertEqual(rn.files_section([]), [])
        build = (ROOT / ".github/workflows/build.yml").read_text()
        self.assertIn("# Tiny, and Manual Release reads it: kept as long as the downloads (7 days).\n"
                      "          retention-days: 7", build)

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
            self.assertTrue(text.startswith("<details>\n<summary>Versi komponen / Component versions</summary>\n"))
            self.assertTrue(text.endswith("</details>\n\n" + rn.components_marker(
                {env["BUILD_VARIANT"]: rn.components(env, LOCK, FEATURES_LOCK) for env in (KSUN, CANDIDATE)}) + "\n"))
            self.assertEqual(text.count("\n### "), 2)
            self.assertIn("@ `aaaaaaaa`", text)

            # Per-release news file + Telegram text.
            news = directory / "news.md"
            news.write_text("Catatan.\n### Baru\n- Varian `KernelSU Next + SUSFS`\n### Diperbaiki\n- Bootloop MediaTek\n")
            files = directory / "files"
            files.mkdir()
            for name in ("1-KERNEL_Cogan-6.1.177_KernelSU-Next+SuSFS_v26.10.16-r3.zip",
                         "2-MANAGER_KernelSU-Next_v3.4.2.apk", "checksums.txt"):
                (files / name).write_text("x")
            telegram = directory / "telegram.txt"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(rn.main(args + ["--files", str(files), "--whats-new-file", str(news),
                                                 "--commit-log", str(directory / "absent"),
                                                 "--title", "Cogan v26.10.16-r3", "--release-type", "Pre-release",
                                                 "--telegram-out", str(telegram)]), 0)
            text = out.getvalue()
            self.assertTrue(text.startswith("> [!TIP]\n> **⭐ Cogan v26.10.16-r3** · Linux 6.1.177 · KernelSU Next"))
            frame_end = text.index("\n\n## Isi rilis")
            box = text[:frame_end]
            self.assertTrue(all(line.startswith(">") for line in box.splitlines()))  # one box
            self.assertIn("> **Fitur unggulan**\n> - 🚀 BBRv3 (default, juga bbr3): internet lebih cepat & stabil", box)
            self.assertIn("> - 🛡️ SUSFS: sembunyikan root dari aplikasi", box)  # from the second variant
            self.assertIn("> **✨ Baru**\n> - Varian `KernelSU Next + SUSFS`", box)
            self.assertIn("> <summary>📋 Salin untuk grup Telegram (Indonesia)</summary>\n>\n> ```text\n> 🚀 Cogan", box)
            # Indonesian first, then the English dropdown, then one Telegram dropdown per language.
            self.assertLess(box.index("**Fitur unggulan**"), box.index("<summary>🇬🇧 English</summary>"))
            self.assertLess(box.index("<summary>🇬🇧 English</summary>"), box.index("(Indonesia)</summary>"))
            self.assertLess(box.index("(Indonesia)</summary>"), box.index("(English)</summary>"))
            self.assertIn("> **Key features**\n> - 🚀 BBRv3 (default, also bbr3): faster, steadier internet", box)
            self.assertIn("> **✨ New**\n> - Varian `KernelSU Next + SUSFS`", box)  # no English line: Indonesian
            self.assertLess(text.index("## Isi rilis"), text.index("<summary>Versi komponen"))
            message = telegram.read_text()
            self.assertTrue(message.startswith("🚀 Cogan v26.10.16-r3 (Pre-release)\n"))
            self.assertIn("• Varian KernelSU Next + SUSFS", message)
            self.assertIn("⭐ Fitur unggulan\n• 🚀 BBRv3 (default, juga bbr3)", message)
            self.assertIn("📦 Kernel + Manager KernelSU-Next v3.4.2\n", message)
            self.assertNotIn("http", message)
            self.assertNotIn("`", message)
            self.assertIn(message.splitlines()[-1], box)

    def test_whats_new_from_file_or_commit_lines(self):
        log = ("fix: something (#80)\n\nBaru: BBRv3 juga bernama bbr3\nDiperbaiki:   Rilis berisi   manager\n"
               "  Baru: BBRv3 juga bernama bbr3\nCo-Authored-By: x\nbukan Baru: ini\n")
        self.assertEqual(rn.whats_new("", log), {"Baru": ["BBRv3 juga bernama bbr3"],
                                                 "Diperbaiki": ["Rilis berisi manager"], "Diperbarui": []})
        override = "### Baru\n- dari file\n### Diperbarui\n- manual\n"
        self.assertEqual(rn.whats_new(override, log), {"Baru": ["dari file"], "Diperbaiki": [], "Diperbarui": ["manual"]})
        self.assertEqual(rn.whats_new_section(rn.whats_new("", "")), [])
        many = "".join(f"Baru: item {i}\n" for i in range(20))
        self.assertEqual(len(rn.whats_new("", many)["Baru"]), rn.MAX_ITEMS)

    def test_telegram_text_is_short_and_plain(self):
        env = dict(KSUN, KSU="BSU", KSU_SUSFS="true")
        features = rn.feature_items("SUSFS, BBRv3 (default, also bbr3), BBG")
        message = rn.telegram_text("Cogan v26.10.20-r4", "Release", [env],
                                   ["1-KERNEL_x.zip", "2-MANAGER_BakaSU_v4.2.0-rc3.apk",
                                    "3-MANAGER-SPOOFED_BakaSU_v4.2.0-rc3.apk", "4-NOMOUNT-MODULE_v2.1.1.zip"],
                                   {"Baru": ["Satu `kode`"], "Diperbaiki": []}, features, ["📦 **Sorotan**"])
        self.assertEqual(message.splitlines()[:4], ["🚀 Cogan v26.10.20-r4 (Rilis)",
                                                    "🐧 Linux 6.1.177 • BakaSU + SUSFS", "", "⭐ Fitur unggulan"])
        self.assertIn("• 📦 Sorotan\n", message)
        self.assertIn("✨ Baru\n• Satu kode\n", message)
        self.assertIn("📦 Kernel + Manager BakaSU v4.2.0-rc3 (biasa/spoofed) + Modul NoMount v2.1.1", message)
        self.assertNotIn("🔧", message)
        self.assertLess(len(message.splitlines()), 20)

    def test_build_features_from_env_or_kernel_zip(self):
        self.assertEqual(rn.feature_items("SUSFS, BBRv3 (default, also bbr3), BBG, NoMount, Full LTO"),
                         ["🛡️ SUSFS: sembunyikan root dari aplikasi",
                          "🚀 BBRv3 (default, juga bbr3): internet lebih cepat & stabil",
                          "🔒 Baseband Guard: lindungi partisi penting", "🧩 NoMount: metamodul tanpa mount",
                          "⚡ Full LTO: kernel lebih ringkas & efisien"])
        self.assertEqual(rn.feature_items("No LTO"), [])
        with tempfile.TemporaryDirectory() as directory:
            kernel = Path(directory) / "1-KERNEL_x.zip"
            with zipfile.ZipFile(kernel, "w") as archive:
                archive.writestr("anykernel.sh", 'ui_print "github.com/cogan17/Cogan"\n'
                                                 'ui_print "Features: SUSFS, BBRv3 (default, also bbr3), Full LTO"\n')
            self.assertEqual(rn.features_from_zip(kernel), "SUSFS, BBRv3 (default, also bbr3), Full LTO")
            self.assertEqual(rn.features_from_zip(Path(directory) / "missing.zip"), "")

    def test_components_per_variant(self):
        ksun = rn.components(KSUN, LOCK, FEATURES_LOCK)
        self.assertEqual(ksun["Kernel"], ["6.1.177", "6.1.177"])
        self.assertEqual(ksun["Manager KernelSU-Next"], [LOCK["KSUN_REF"], LOCK["KSUN_REF"]])
        self.assertEqual(ksun["NoMount"], [LOCK["NOMOUNT_COMMIT"][:8], LOCK["NOMOUNT_REF"]])
        self.assertEqual(ksun["Neutron Clang"], [LOCK["NEUTRON_RELEASE"]] * 2)
        self.assertNotIn("SUSFS", ksun)
        candidate = rn.components(dict(CANDIDATE, SUSFS_VERSION="v2.3.0"), LOCK, FEATURES_LOCK)
        self.assertEqual(candidate["SUSFS"], ["99999999", "v2.3.0 (99999999)"])
        self.assertEqual(candidate["Baseband Guard"][0], rn.feature_commit(FEATURES_LOCK, "bbg")[:8])
        no_bbg = rn.components(dict(KSUN, KERNEL_FEATURES="NoMount, Full LTO"), LOCK, FEATURES_LOCK)
        self.assertNotIn("Baseband Guard", no_bbg)

    def test_updates_against_the_previous_release(self):
        previous = {"Kernel": ["6.1.177", "6.1.177"], "Manager KernelSU-Next": ["v3.4.2", "v3.4.2"],
                    "SUSFS": ["5369359d", "v2.3.0 (5369359d)"], "Gone": ["x", "x"]}
        current = {"Kernel": ["6.1.180", "6.1.180"], "Manager KernelSU-Next": ["v3.4.2", "v3.4.2"],
                   "SUSFS": ["abcdef12", "v2.4.0 (abcdef12)"], "New": ["y", "y"]}
        self.assertEqual(rn.updates(previous, current),
                         ["Kernel 6.1.177 → 6.1.180", "SUSFS v2.3.0 (5369359d) → v2.4.0 (abcdef12)"])
        self.assertEqual(rn.updates({}, current), [])
        marker = rn.components_marker({"6.1-KSUN": current})
        self.assertEqual(rn.read_previous_components("text\n" + marker + "\n"), {"6.1-KSUN": current})
        self.assertEqual(rn.read_previous_components("no marker"), {})
        self.assertEqual(rn.read_previous_components("<!-- cogan-components: {bad} -->"), {})
        self.assertEqual(rn.components_marker({"a": {"b": ["--", "x"]}}), "")

    def test_cli_lists_updates_in_the_box_and_telegram(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "env").mkdir()
            (directory / "env" / "build-env-6.1-KSUN.txt").write_text(
                "".join(f"{key}={value}\n" for key, value in dict(KSUN, LINUX_VERSION="6.1.180").items()))
            old = rn.components(KSUN, LOCK, FEATURES_LOCK)
            old["Manager KernelSU-Next"] = ["v3.4.1", "v3.4.1"]
            (directory / "previous.md").write_text("> [!TIP]\n...\n" + rn.components_marker({"6.1-KSUN": old}) + "\n")
            telegram = directory / "telegram.txt"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(rn.main(["--lock", str(ROOT / "configs/upstream.lock"),
                                          "--features-lock", str(ROOT / "configs/ksun-susfs-6.1-features.lock.json"),
                                          "--source-sha", SHA, "--repo", REPO, "--env-dir", str(directory / "env"),
                                          "--previous-notes", str(directory / "previous.md"),
                                          "--title", "Cogan v26.10.20-r4", "--release-type", "Release",
                                          "--telegram-out", str(telegram)]), 0)
            text = out.getvalue()
            box = text[:text.index("\n\n<details>\n<summary>Versi komponen")]
            self.assertIn("> **⬆️ Diperbarui**\n> - Kernel 6.1.177 → 6.1.180\n"
                          f"> - Manager KernelSU-Next v3.4.1 → {LOCK['KSUN_REF']}", box)
            self.assertIn(f"⬆️ Diperbarui\n• Kernel 6.1.177 → 6.1.180\n• Manager KernelSU-Next v3.4.1 → {LOCK['KSUN_REF']}",
                          telegram.read_text())
            self.assertIn('"Kernel":["6.1.180","6.1.180"]', text)  # recorded for the next release

    def test_english_news_features_and_telegram(self):
        log = "Baru: Fitur A\nNew: Feature A\nDiperbaiki: Perbaikan B\nUpdated: manual update\n"
        self.assertEqual(rn.whats_new("", log, "en"), {"Baru": ["Feature A"], "Diperbaiki": [], "Diperbarui": ["manual update"]})
        self.assertEqual(rn.whats_new("", log), {"Baru": ["Fitur A"], "Diperbaiki": ["Perbaikan B"], "Diperbarui": []})
        r3 = (ROOT / "docs/whats-new/v26.10.16-r3.md").read_text()
        self.assertEqual(len(rn.whats_new(r3, "", "en")["Baru"]), len(rn.whats_new(r3)["Baru"]))
        self.assertTrue(rn.whats_new(r3, "", "en")["Baru"][0].startswith("KernelSU Next + SUSFS variant"))
        self.assertEqual(rn.feature_items("SUSFS, Thin LTO", "en"),
                         ["🛡️ SUSFS: hides root from apps", "⚡ Thin LTO: leaner, more efficient kernel"])
        highlights = (ROOT / "docs/whats-new/highlights.md").read_text()
        self.assertTrue(rn.read_highlights(highlights, "en")[0].startswith("📦 The manager and NoMount module"))
        self.assertTrue(rn.read_highlights(highlights)[0].startswith("📦 Manager + modul NoMount"))
        self.assertEqual(rn.read_highlights("- hanya Indonesia\n", "en"), ["hanya Indonesia"])
        message = rn.telegram_text("Cogan v1", "Release", [KSUN], ["1-KERNEL_x.zip", "4-NOMOUNT-MODULE_v2.1.1.zip"],
                                   {"Baru": ["Feature A"]}, [], [], "en")
        self.assertEqual(message.splitlines()[0], "🚀 Cogan v1 (Release)")
        self.assertIn("✨ New\n• Feature A", message)
        self.assertIn("📦 Kernel + NoMount module v2.1.1\n⚠️ Keep your stock boot.img before flashing.", message)

    def test_highlights_file_is_short(self):
        for lang in ("id", "en"):
            highlights = rn.read_highlights((ROOT / "docs/whats-new/highlights.md").read_text(), lang)
            self.assertTrue(1 <= len(highlights) <= 4)
            self.assertTrue(all("SUSFS" not in line and "BBR" not in line for line in highlights))

    def test_r3_news_file_parses(self):
        items = rn.whats_new((ROOT / "docs/whats-new/v26.10.16-r3.md").read_text())
        self.assertTrue(items["Baru"] and items["Diperbaiki"])
        self.assertLessEqual(sum(map(len, items.values())), 8)


if __name__ == "__main__":
    unittest.main()
