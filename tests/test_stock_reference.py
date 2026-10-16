#!/usr/bin/env python3
"""Offline tests for the stock kernel reference fetch (a local repository stands in for ACK)."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import stock_reference as sr


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


class StockReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.ack = base / "ack"
        for path, text in (("Makefile", "VERSION = 6\nPATCHLEVEL = 1\nSUBLEVEL = 138\n"),
                           ("build.config.common", "KMI_GENERATION=11\n"),
                           ("android/abi_gki_aarch64_mtk", "[abi_symbol_list]\n  x\n"),
                           ("include/trace/hooks/sched.h", "DECLARE_HOOK(android_vh_x, a, b);\n"),
                           ("mm/shmem.c", "not needed by the gate\n")):
            (self.ack / path).parent.mkdir(parents=True, exist_ok=True)
            (self.ack / path).write_text(text)
        git(self.ack.parent, "init", "-q", str(self.ack))
        git(self.ack, "config", "uploadpack.allowFilter", "true")
        git(self.ack, "config", "uploadpack.allowAnySHA1InWant", "true")
        git(self.ack, "add", ".")
        git(self.ack, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "stock")
        self.commit = git(self.ack, "rev-parse", "HEAD")
        self.dest = base / "stock"

    def fetch(self, **stock):
        pinned = dict(sr.DEVICES["rothko"]["stock"], commit=self.commit, **stock)
        with mock.patch.dict(sr.DEVICES["rothko"], {"stock": pinned}):
            return sr.main(["--device", "rothko", str(self.dest), "--repo", self.ack.as_uri()])

    def test_fetches_only_what_the_gate_reads_at_the_pinned_commit(self):
        self.assertEqual(self.fetch(), 0)
        self.assertEqual(git(self.dest, "rev-parse", "HEAD"), self.commit)
        self.assertTrue((self.dest / "android/abi_gki_aarch64_mtk").is_file())
        self.assertTrue((self.dest / "include/trace/hooks/sched.h").is_file())
        self.assertFalse((self.dest / "mm").exists())

    def test_wrong_version_or_used_destination_is_refused(self):
        self.assertEqual(self.fetch(version="6.1.155"), 1)
        self.assertEqual(self.fetch(), 1)  # destination no longer empty

    def test_rothko_pins_the_stock_kernel_commit(self):
        stock = sr.DEVICES["rothko"]["stock"]
        self.assertEqual(stock["commit"], "6ab8c9a86a331cece499c7edac062ceffbe2e320")
        self.assertTrue(stock["kernel"].startswith(stock["version"] + "-android14-11-g" + stock["commit"][:12]))


if __name__ == "__main__":
    unittest.main()
