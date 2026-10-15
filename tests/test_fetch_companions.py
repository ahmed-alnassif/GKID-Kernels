#!/usr/bin/env python3
"""Offline tests for fetch_companions.py: matching manager APK and NoMount module."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import fetch_companions as fc

ROOT = Path(__file__).resolve().parents[1]
# The real pins without any recorded release tags/assets; each test adds its own.
REAL_LOCK = "".join(line + "\n" for line in (ROOT / "configs/upstream.lock").read_text().splitlines()
                    if line.split("=", 1)[0] not in fc.mu.ANCHORS)
APK, ZIP = b"official manager apk", b"official nomount module"
FIXTURE = {
    "KSU_REF": "v3.3.1", "KSU_MANAGER_APK": "KernelSU_v3.3.1_32211-release.apk",
    "KSU_MANAGER_SHA256": hashlib.sha256(APK).hexdigest(),
    "KSUN_MANAGER_APK": "KernelSU_Next_v3.4.2_33355-release.apk",
    "KSUN_MANAGER_SHA256": hashlib.sha256(APK).hexdigest(),
    "NOMOUNT_REF": "v2.1.1", "NOMOUNT_MODULE_ZIP": "NoMount-v2.1.1-release.zip",
    "NOMOUNT_MODULE_SHA256": hashlib.sha256(ZIP).hexdigest(),
}


class FetchCompanionsTests(unittest.TestCase):
    def run_main(self, ksu, susfs="true", lock_updates=FIXTURE, tags=None, files=None):
        lock_text = fc.mu.write_lock(REAL_LOCK, dict(lock_updates))
        lock = fc.mu.read_lock(lock_text)
        tags = tags or {"tiann/KernelSU": lock["KSU_COMMIT"], "KernelSU-Next/KernelSU-Next": lock["KSUN_COMMIT"],
                        "maxsteeel/nomount": lock["NOMOUNT_COMMIT"]}
        files = files or {}
        fetched = []

        def lister(url, *patterns, **_):
            repo = url[len("https://github.com/"):-len(".git")]
            return {patterns[0]: tags[repo]}

        def fetch(url):
            fetched.append(url)
            name = url.rsplit("/", 1)[1]
            return files.get(name, ZIP if name.endswith(".zip") else APK)

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "upstream.lock").write_text(lock_text)
            output, summary = directory / "out.txt", directory / "summary.md"
            with mock.patch.object(fc.mu, "LOCK", directory / "upstream.lock"):
                status = fc.main(["--ksu", ksu, "--susfs", susfs, "--prefix", "Cogan-KernelSU+SuSFS",
                                  "--out", str(directory / "companions"), "--github-output", str(output),
                                  "--summary", str(summary)], lister=lister, fetch=fetch)
            outputs = dict(line.split("=", 1) for line in output.read_text().splitlines()) if output.exists() else {}
            saved = sorted(p.name for p in (directory / "companions").glob("*")) \
                if (directory / "companions").exists() else []
            return status, outputs, saved, summary.read_text(), fetched

    def test_kernelsu_gets_its_release_manager_and_nomount_module(self):
        status, outputs, saved, summary, fetched = self.run_main("KSU")
        self.assertEqual(status, 0, summary)
        self.assertEqual(saved, ["Cogan-KernelSU+SuSFS-KernelSU_v3.3.1_32211-release.apk",
                                 "Cogan-KernelSU+SuSFS-NoMount-v2.1.1-release.zip"])
        self.assertEqual(set(outputs), {"manager", "nomount"})
        self.assertIn("https://github.com/tiann/KernelSU/releases/download/v3.3.1/"
                      "KernelSU_v3.3.1_32211-release.apk", fetched)
        self.assertIn("KernelSU v3.3.1", summary)

    def test_wrong_checksum_fails_and_keeps_nothing(self):
        status, outputs, saved, summary, _ = self.run_main(
            "KSU", files={"KernelSU_v3.3.1_32211-release.apk": b"tampered"})
        self.assertEqual(status, 1)
        self.assertNotIn("manager", outputs)
        self.assertNotIn("Cogan-KernelSU+SuSFS-KernelSU_v3.3.1_32211-release.apk", saved)
        self.assertIn("does not match the pinned", summary)

    def test_moved_tag_fails_before_download(self):
        lock = fc.mu.read_lock(REAL_LOCK)
        status, _, _, summary, fetched = self.run_main(
            "KSU", tags={"tiann/KernelSU": "f" * 40, "maxsteeel/nomount": lock["NOMOUNT_COMMIT"]})
        self.assertEqual(status, 1)
        self.assertIn("now points at", summary)
        self.assertFalse(any("tiann/KernelSU" in url for url in fetched))

    def test_vanilla_gets_nothing(self):
        status, outputs, saved, summary, fetched = self.run_main("no", susfs="false")
        self.assertEqual((status, outputs, saved, fetched), (0, {}, [], []))
        self.assertIn("Vanilla build", summary)

    def test_pins_without_assets_are_skipped_with_a_hint(self):
        status, outputs, _, summary, fetched = self.run_main("BSU", lock_updates={})
        self.assertEqual((status, outputs, fetched), (0, {}, []))
        self.assertIn("run **Cogan Manual Update**", summary)

    def test_test_build_gets_official_ksun_manager_without_tag_check(self):
        lock = fc.mu.read_lock(REAL_LOCK)
        status, outputs, saved, summary, _ = self.run_main(
            "KSUN", tags={"maxsteeel/nomount": lock["NOMOUNT_COMMIT"]})
        self.assertEqual(status, 0, summary)
        self.assertIn("pershoot fork", summary)
        self.assertEqual(set(outputs), {"manager", "nomount"})  # candidate NoMount is v2.1.1 too
        self.assertEqual(fc.candidate_nomount_commit(), lock["NOMOUNT_COMMIT"])


if __name__ == "__main__":
    unittest.main()
