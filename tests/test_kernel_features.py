#!/usr/bin/env python3
"""Offline tests for kernel_features.py: the feature line comes from the built config."""
import tempfile
import unittest
from pathlib import Path

from scripts import kernel_features as kf

FULL = """CONFIG_KSU=y
CONFIG_KSU_SUSFS=y
CONFIG_TCP_CONG_BBR=y
CONFIG_DEFAULT_BBR=y
CONFIG_DEFAULT_TCP_CONG="bbr"
CONFIG_BBG=y
CONFIG_NOMOUNT=y
CONFIG_LTO_CLANG_FULL=y
# CONFIG_LTO_CLANG_THIN is not set
"""
BBR_V3_SOURCE = "/* BBR v3 */\n#define BBR_VERSION\t\t3\n"


class KernelFeaturesTests(unittest.TestCase):
    def test_full_ksun_susfs_build(self):
        self.assertEqual(kf.features(FULL, BBR_V3_SOURCE),
                         ["SUSFS", "BBRv3 (default)", "BBG", "NoMount", "Full LTO"])

    def test_plain_bbr_without_the_v3_patch(self):
        self.assertEqual(kf.features(FULL, "/* stock tcp_bbr.c */\n")[1], "BBR (default)")

    def test_bbr_built_but_not_default(self):
        config = FULL.replace('CONFIG_DEFAULT_TCP_CONG="bbr"', 'CONFIG_DEFAULT_TCP_CONG="cubic"')
        self.assertIn("BBRv3", kf.features(config, BBR_V3_SOURCE))

    def test_networking_off_vanilla_thin_lto(self):
        config = "# CONFIG_TCP_CONG_BBR is not set\nCONFIG_LTO_CLANG_THIN=y\n"
        self.assertEqual(kf.features(config, BBR_V3_SOURCE), ["Thin LTO"])
        self.assertEqual(kf.features("", ""), ["No LTO"])

    def test_cli_writes_github_env(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / ".config").write_text(FULL)
            (directory / "src/net/ipv4").mkdir(parents=True)
            (directory / "src/net/ipv4/tcp_bbr.c").write_text(BBR_V3_SOURCE)
            env = directory / "env"
            self.assertEqual(kf.main([str(directory / ".config"), str(directory / "src"),
                                      "--github-env", str(env)]), 0)
            self.assertEqual(env.read_text(),
                             "KERNEL_FEATURES=SUSFS, BBRv3 (default), BBG, NoMount, Full LTO\n")
            self.assertEqual(kf.main([str(directory / "missing"), str(directory / "src")]), 1)


if __name__ == "__main__":
    unittest.main()
