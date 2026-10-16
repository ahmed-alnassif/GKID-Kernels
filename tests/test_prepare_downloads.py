#!/usr/bin/env python3
"""Offline tests for prepare_downloads.py: clear names, matching manager/NoMount, summary."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import prepare_downloads as pd

ROOT = Path(__file__).resolve().parents[1]
# The real pins without any recorded release tags/assets; each test adds its own.
REAL_LOCK = "".join(line + "\n" for line in (ROOT / "configs/upstream.lock").read_text().splitlines()
                    if line.split("=", 1)[0] not in pd.mu.ANCHORS)
APK, SPOOFED, ZIP = b"official manager apk", b"official spoofed apk", b"official nomount module"
FIXTURE = {
    "KSU_REF": "v3.3.1", "KSU_MANAGER_APK": "KernelSU_v3.3.1_32680-release.apk",
    "KSU_MANAGER_SHA256": hashlib.sha256(APK).hexdigest(),
    "BSU_REF": "v4.2.0-rc3", "BSU_MANAGER_APK": "ReSukiSU_v4.2.0-rc3_35171-universal-release.apk",
    "BSU_MANAGER_SHA256": hashlib.sha256(APK).hexdigest(),
    "KSUN_MANAGER_APK": "KernelSU_Next_v3.4.2_33355-release.apk",
    "KSUN_MANAGER_SHA256": hashlib.sha256(APK).hexdigest(),
    "KSUN_SPOOFED_APK": "KernelSU_Next_v3.4.2_33355-spoofed-release.apk",
    "KSUN_SPOOFED_SHA256": hashlib.sha256(SPOOFED).hexdigest(),
    "NOMOUNT_REF": "v2.1.1", "NOMOUNT_MODULE_ZIP": "NoMount-v2.1.1-release-7046c7a-555.zip",
    "NOMOUNT_MODULE_SHA256": hashlib.sha256(ZIP).hexdigest(),
}
KERNEL_URL, SUSFS_URL = pd.mu.PINS["KERNEL_COMMIT_6_1"][2], pd.mu.PINS["SUSFS_COMMIT_6_1"][2]
NEW = "c" * 40


def makefile(sublevel):
    return f"VERSION = 6\nPATCHLEVEL = 1\nSUBLEVEL = {sublevel}\nEXTRAVERSION =\n"


def susfs_header(version):
    return f'#ifndef KSU_SUSFS_H\n#define KSU_SUSFS_H\n#define SUSFS_VERSION "{version}"\n'


class PrepareDownloadsTests(unittest.TestCase):
    def run_main(self, ksu, susfs="false", variant="BakaSU+SuSFS", lock_updates=FIXTURE, tags=None,
                 files=None, upstream=None, suffix="", kernel=True, heads=None, texts=None, name=None):
        lock_text = pd.mu.write_lock(REAL_LOCK, dict(lock_updates))
        lock = pd.mu.read_lock(lock_text)
        tags = tags or {"tiann/KernelSU": lock["KSU_COMMIT"], "Baka-SU/BakaSU": lock["BSU_COMMIT"],
                        "KernelSU-Next/KernelSU-Next": lock["KSUN_COMMIT"],
                        "maxsteeel/nomount": lock["NOMOUNT_COMMIT"]}
        files = files or {}
        fetched = []
        pinned_tags = {pd.mu.PINS[key][2]: (lock.get(tag_key), lock[key])
                       for key, tag_key in pd.mu.TAG_KEYS.items()}

        branches = {KERNEL_URL: lock["KERNEL_COMMIT_6_1"], SUSFS_URL: lock["SUSFS_COMMIT_6_1"], **(heads or {})}
        texts = texts or {}

        def lister(url, *patterns, options=()):
            if "--tags" in options:  # upstream release list: the pinned tag plus any newer one
                tag, commit = pinned_tags[url]
                return {**({f"refs/tags/{tag}": commit} if tag else {}), **(upstream or {}).get(url, {})}
            if url in branches:  # branch-pinned kernel / SUSFS: same as the lock unless overridden
                if isinstance(branches[url], Exception):
                    raise branches[url]
                return {patterns[0]: branches[url]}
            repo = url[len("https://github.com/"):-len(".git")]
            return {patterns[0]: tags[repo]}

        def text_fetch(url):
            fetched.append(url)
            for commit, text in texts.items():
                if f"/{commit}/" in url:
                    return text
            raise OSError("not served: " + url)

        def fetch(url):
            fetched.append(url)
            name = url.rsplit("/", 1)[1]
            if name in files:
                return files[name]
            return ZIP if name.endswith(".zip") else SPOOFED if "spoofed" in name else APK

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "upstream.lock").write_text(lock_text)
            artifacts = directory / "artifacts"
            artifacts.mkdir()
            if kernel:
                (artifacts / f"Cogan-{variant}-v26.10.16-r15-6.1.177.zip").write_bytes(b"kernel")
            (artifacts / "build.log").write_text("log")
            output, summary = directory / "out.txt", directory / "summary.md"
            with mock.patch.object(pd.mu, "LOCK", directory / "upstream.lock"):
                status = pd.main(["--ksu", ksu, "--susfs", susfs, "--variant", variant,
                                  "--release", "v26.10.16-r15", "--linux-version", "6.1.177",
                                  "--artifacts", str(artifacts), "--out", str(directory / "downloads"),
                                  "--suffix", suffix, "--github-output", str(output), "--summary", str(summary),
                                  *(["--name", name] if name else [])],
                                 lister=lister, fetch=fetch, text_fetch=text_fetch)
            outputs = dict(line.split("=", 1) for line in output.read_text().splitlines()) if output.exists() else {}
            saved = sorted(p.name for p in (directory / "downloads").glob("*")) \
                if (directory / "downloads").exists() else []
            return status, outputs, saved, summary.read_text(), fetched

    def test_rothko_kernel_download_carries_the_device_name(self):
        status, outputs, saved, summary, _ = self.run_main("BSU", susfs="true", name="Cogan-Rothko")
        self.assertEqual(status, 0, summary)
        self.assertIn("1-KERNEL_Cogan-Rothko-6.1.177_BakaSU+SuSFS_v26.10.16-r15.zip", saved)
        self.assertIn("Kernel Cogan-Rothko 6.1.177 (BakaSU+SuSFS)", summary)
        status, _, saved, summary, _ = self.run_main("BSU", susfs="true", name="Cogan Rothko")
        self.assertEqual(status, 1)
        self.assertEqual(saved, [])

    def test_bakasu_downloads_are_numbered_and_named_by_what_they_are(self):
        status, outputs, saved, summary, fetched = self.run_main("BSU")
        self.assertEqual(status, 0, summary)
        self.assertEqual(saved, ["1-KERNEL_Cogan-6.1.177_BakaSU+SuSFS_v26.10.16-r15.zip",
                                 "2-MANAGER_BakaSU_v4.2.0-rc3.apk",
                                 "4-NOMOUNT-MODULE_v2.1.1.zip"])
        self.assertEqual(set(outputs), {"kernel", "manager", "nomount"})
        self.assertIn("| 1 | `1-KERNEL_Cogan-6.1.177_BakaSU+SuSFS_v26.10.16-r15.zip` |", summary)
        self.assertIn("Kernel Flasher", summary)
        self.assertIn("belum ada manager spoofed resmi yang dipin", summary)  # none pinned in this fixture
        self.assertIn("https://github.com/Baka-SU/BakaSU/releases/download/v4.2.0-rc3/"
                      "ReSukiSU_v4.2.0-rc3_35171-universal-release.apk", fetched)
        self.assertIn("Abaikan / ignore `build-…`", summary)

    def test_bakasu_spoofed_is_downloaded_from_the_mirror_of_the_tag_run(self):
        name = "BakaSU-spoofed_ReSukiSU_v4.2.0-rc3_35171-universal-release.apk"
        updates = {**FIXTURE, "BSU_SPOOFED_APK": name, "BSU_SPOOFED_SHA256": hashlib.sha256(SPOOFED).hexdigest()}
        with mock.patch.dict("os.environ", {"GITHUB_REPOSITORY": "cogan17/Cogan"}):
            status, outputs, saved, summary, fetched = self.run_main(
                "BSU", lock_updates=updates, files={name: SPOOFED})
        self.assertEqual(status, 0, summary)
        self.assertIn("3-MANAGER-SPOOFED_BakaSU_v4.2.0-rc3.apk", saved)
        self.assertEqual(set(outputs), {"kernel", "manager", "spoofed", "nomount"})
        self.assertIn(f"https://github.com/cogan17/Cogan/releases/download/cogan-mirror/{name}", fetched)
        self.assertNotIn("belum ada manager spoofed", summary)
        # The rothko builder runs in cogan17/Xiomi-14t-pro and still uses Cogan's mirror.
        with mock.patch.dict("os.environ", {"GITHUB_REPOSITORY": "cogan17/Xiomi-14t-pro",
                                            "COGAN_MIRROR_REPO": "cogan17/Cogan"}):
            status, _, saved, summary, fetched = self.run_main("BSU", lock_updates=updates, files={name: SPOOFED})
        self.assertEqual(status, 0, summary)
        self.assertIn(f"https://github.com/cogan17/Cogan/releases/download/cogan-mirror/{name}", fetched)

    def test_kernelsu_next_ships_normal_and_spoofed_manager(self):
        status, outputs, saved, summary, _ = self.run_main("KSUN", variant="KernelSU-Next")
        self.assertEqual(status, 0, summary)
        self.assertEqual(saved, ["1-KERNEL_Cogan-6.1.177_KernelSU-Next_v26.10.16-r15.zip",
                                 "2-MANAGER_KernelSU-Next_v3.4.2.apk",
                                 "3-MANAGER-SPOOFED_KernelSU-Next_v3.4.2.apk",
                                 "4-NOMOUNT-MODULE_v2.1.1.zip"])
        self.assertEqual(set(outputs), {"kernel", "manager", "spoofed", "nomount"})
        self.assertIn("pilih 2 **atau** 3", summary)

    def test_multi_variant_runs_get_a_suffix_so_names_never_collide(self):
        _, _, saved, _, _ = self.run_main("KSU", variant="KernelSU+SuSFS", suffix="_6.1-KSU+SUSFS")
        self.assertIn("2-MANAGER_KernelSU_v3.3.1_6.1-KSU+SUSFS.apk", saved)
        self.assertIn("4-NOMOUNT-MODULE_v2.1.1_6.1-KSU+SUSFS.zip", saved)

    def test_wrong_checksum_fails_but_the_kernel_is_still_prepared(self):
        status, outputs, saved, summary, _ = self.run_main(
            "KSU", variant="KernelSU", files={"KernelSU_v3.3.1_32680-release.apk": b"tampered"})
        self.assertEqual(status, 1)
        self.assertIn("kernel", outputs)
        self.assertNotIn("manager", outputs)
        self.assertNotIn("2-MANAGER_KernelSU_v3.3.1.apk", saved)
        self.assertIn("does not match the pinned", summary)

    def test_moved_tag_fails_before_download(self):
        lock = pd.mu.read_lock(REAL_LOCK)
        status, _, _, summary, fetched = self.run_main(
            "KSU", variant="KernelSU", tags={"tiann/KernelSU": "f" * 40, "maxsteeel/nomount": lock["NOMOUNT_COMMIT"]})
        self.assertEqual(status, 1)
        self.assertIn("now points at", summary)
        self.assertFalse(any("tiann/KernelSU" in url for url in fetched))

    def test_vanilla_gets_only_the_kernel(self):
        status, outputs, saved, summary, fetched = self.run_main("no", variant="Vanilla")
        self.assertEqual((status, list(outputs), fetched), (0, ["kernel"], []))
        self.assertEqual(saved, ["1-KERNEL_Cogan-6.1.177_Vanilla_v26.10.16-r15.zip"])
        self.assertIn("Vanilla", summary)

    def test_pins_without_assets_are_skipped_with_a_hint(self):
        status, outputs, _, summary, fetched = self.run_main("BSU", lock_updates={})
        self.assertEqual((status, list(outputs), fetched), (0, ["kernel"], []))
        self.assertIn("**Cogan Manual Update** → `update` → `root-managers`", summary)

    def test_test_build_gets_official_ksun_managers_without_tag_check(self):
        lock = pd.mu.read_lock(REAL_LOCK)
        status, outputs, _, summary, _ = self.run_main(
            "KSUN", susfs="true", variant="KernelSU-Next+SuSFS",
            tags={"maxsteeel/nomount": lock["NOMOUNT_COMMIT"]})
        self.assertEqual(status, 0, summary)
        self.assertIn("fork pershoot", summary)
        self.assertEqual(set(outputs), {"kernel", "manager", "spoofed", "nomount"})
        self.assertEqual(pd.candidate_nomount_commit(), lock["NOMOUNT_COMMIT"])

    def test_summary_credits_manual_update_and_reminds_about_newer_releases(self):
        status, _, _, summary, _ = self.run_main("BSU")
        self.assertIn("dikunci bersama oleh **Cogan Manual Update**", summary)
        self.assertNotIn("Pengingat", summary)
        newer = {pd.mu.PINS["BSU_COMMIT"][2]: {"refs/tags/v4.2.0": "e" * 40},
                 pd.mu.PINS["NOMOUNT_COMMIT"][2]: {"refs/tags/v2.2.0": "f" * 40}}
        status, outputs, _, summary, _ = self.run_main("BSU", upstream=newer)
        self.assertEqual(status, 0, summary)  # a reminder never fails the build
        self.assertIn("BakaSU v4.2.0 tersedia", summary)
        self.assertIn("`update` → `root-managers`", summary)
        self.assertIn("NoMount v2.2.0 tersedia", summary)

    def test_reminds_about_a_new_kernel_sublevel(self):
        status, _, _, summary, fetched = self.run_main(
            "BSU", heads={KERNEL_URL: NEW}, texts={NEW: makefile(180)})
        self.assertEqual(status, 0, summary)  # a reminder never fails the build
        self.assertIn("Kernel GKID 6.1.180 tersedia / available (lts terpasang / pinned: 6.1.177)", summary)
        self.assertIn("`update` → `kernel-6.1`", summary)
        self.assertIn(f"ahmed-alnassif/GKI-Duchamp-6.1/{NEW}/Makefile", " ".join(fetched))

    def test_new_kernel_commit_on_the_same_sublevel_is_reported_as_a_commit(self):
        _, _, _, summary, _ = self.run_main("BSU", heads={KERNEL_URL: NEW}, texts={NEW: makefile(177)})
        self.assertIn(f"Kernel GKID 6.1.177 punya commit baru / has a new commit `{NEW[:12]}`", summary)
        _, _, _, summary, _ = self.run_main("BSU", heads={KERNEL_URL: NEW})  # Makefile unreadable
        self.assertIn(f"Kernel GKID 6.1 punya commit baru / has a new commit `{NEW[:12]}`", summary)

    def test_vanilla_also_gets_the_kernel_reminder(self):
        status, outputs, _, summary, _ = self.run_main(
            "no", variant="Vanilla", heads={KERNEL_URL: NEW}, texts={NEW: makefile(180)})
        self.assertEqual((status, list(outputs)), (0, ["kernel"]))
        self.assertIn("Kernel GKID 6.1.180 tersedia", summary)

    def test_reminds_about_a_new_susfs_version_on_susfs_builds_only(self):
        pinned = pd.mu.read_lock(REAL_LOCK)["SUSFS_COMMIT_6_1"]
        texts = {pinned: susfs_header("v2.3.0"), NEW: susfs_header("v2.3.1")}
        status, _, _, summary, fetched = self.run_main("BSU", susfs="true", heads={SUSFS_URL: NEW}, texts=texts)
        self.assertEqual(status, 0, summary)
        self.assertIn("SUSFS v2.3.1 tersedia / available (terpasang / pinned: v2.3.0)", summary)
        self.assertIn("`update` → `susfs`", summary)
        self.assertIn(f"susfs4ksu/-/raw/{NEW}/kernel_patches/include/linux/susfs.h", " ".join(fetched))
        _, _, _, summary, _ = self.run_main("KSU", variant="KernelSU", heads={SUSFS_URL: NEW}, texts=texts)
        self.assertNotIn("SUSFS v2.3.1", summary)  # no SUSFS in this kernel

    def test_new_susfs_commit_with_the_same_version_names_the_commit(self):
        pinned = pd.mu.read_lock(REAL_LOCK)["SUSFS_COMMIT_6_1"]
        texts = {pinned: susfs_header("v2.3.0"), NEW: susfs_header("v2.3.0")}
        _, _, _, summary, _ = self.run_main("BSU", susfs="true", heads={SUSFS_URL: NEW}, texts=texts)
        self.assertIn(f"SUSFS 6.1 punya commit baru / has a new commit `{NEW[:12]}` "
                      f"(terpasang / pinned: `{pinned[:12]}`, v2.3.0)", summary)

    def test_frozen_test_kernel_gets_no_kernel_or_susfs_reminder(self):
        lock = pd.mu.read_lock(REAL_LOCK)
        _, _, _, summary, _ = self.run_main(
            "KSUN", susfs="true", variant="KernelSU-Next+SuSFS",
            tags={"maxsteeel/nomount": lock["NOMOUNT_COMMIT"]},
            heads={KERNEL_URL: NEW, SUSFS_URL: NEW}, texts={NEW: makefile(180)})
        self.assertNotIn("Kernel GKID", summary)
        self.assertNotIn("SUSFS 6.1 punya", summary)

    def test_unreachable_upstream_never_fails_the_build(self):
        status, _, _, summary, _ = self.run_main(
            "BSU", susfs="true", heads={KERNEL_URL: OSError("down"), SUSFS_URL: OSError("down")})
        self.assertEqual(status, 0, summary)
        self.assertNotIn("Pengingat", summary)

    def test_unexpected_reminder_error_still_ships_the_kernel(self):
        with mock.patch.object(pd, "kernel_reminder", side_effect=RuntimeError("bug")):
            status, outputs, _, summary, _ = self.run_main("BSU")
        self.assertEqual(status, 0, summary)
        self.assertIn("kernel", outputs)
        self.assertIn("could not be checked (RuntimeError)", summary)

    def test_missing_kernel_zip_is_reported(self):
        status, outputs, _, summary, _ = self.run_main("BSU", kernel=False)
        self.assertNotIn("kernel", outputs)
        self.assertIn("expected one ZIP", summary)


if __name__ == "__main__":
    unittest.main()
