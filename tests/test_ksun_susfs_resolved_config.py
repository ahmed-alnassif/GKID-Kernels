#!/usr/bin/env python3
"""Offline unit tests for the KSUN/SUSFS resolved-config gate; no kernel build."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/check_ksun_susfs_resolved_config.py"
spec = importlib.util.spec_from_file_location("resolved_gate", MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

LOCK = {
    "configuration": {
        "required": {
            "CONFIG_KSU": "y",
            "CONFIG_KSU_SUSFS": "y",
            "CONFIG_BBG": "y",
            "CONFIG_NOMOUNT": "y",
            "CONFIG_LTO_CLANG_FULL": "y",
            "CONFIG_CFI_CLANG": "y",
        },
        "forbidden": ["CONFIG_NTSYNC", "CONFIG_LTO_CLANG_THIN", "CONFIG_BBG_BLOCK_BOOT"],
    }
}

GOOD = """CONFIG_KSU=y
CONFIG_KSU_SUSFS=y
CONFIG_BBG=y
CONFIG_NOMOUNT=y
CONFIG_LTO_CLANG_FULL=y
CONFIG_CFI_CLANG=y
CONFIG_LSM="landlock,selinux,baseband_guard"
# CONFIG_NTSYNC is not set
# CONFIG_LTO_CLANG_THIN is not set
# CONFIG_BBG_BLOCK_BOOT is not set
"""


class ResolvedConfigTests(unittest.TestCase):
    def check(self, value):
        return gate.audit(value.encode("utf-8"), LOCK)

    def test_valid(self):
        self.assertEqual([], self.check(GOOD))

    def test_missing_required(self):
        self.assertTrue(any("CONFIG_NOMOUNT" in error for error in
                            self.check(GOOD.replace("CONFIG_NOMOUNT=y\n", ""))))

    def test_forbidden_enabled(self):
        self.assertTrue(any("CONFIG_NTSYNC" in error for error in
                            self.check(GOOD.replace("# CONFIG_NTSYNC is not set",
                                                    "CONFIG_NTSYNC=y"))))

    def test_missing_bbg_lsm(self):
        self.assertTrue(any("CONFIG_LSM" in error for error in
                            self.check(GOOD.replace(",baseband_guard", ""))))

    def test_duplicate_key(self):
        with self.assertRaises(ValueError):
            self.check(GOOD + "CONFIG_BBG=n\n")

    def test_susfs_without_ksu(self):
        self.assertTrue(any("CONFIG_KSU" in error for error in
                            self.check(GOOD.replace("CONFIG_KSU=y", "CONFIG_KSU=n"))))

    def test_locked_fragment_subfeature_missing(self):
        import hashlib
        from unittest.mock import patch
        fragment = b"CONFIG_KSU_SUSFS_SUS_PATH=y\n"
        lock = {"configuration": {**LOCK["configuration"],
                "fragment": "configs/ksun-susfs-6.1-features.config",
                "sha256": hashlib.sha256(fragment).hexdigest()}}
        with patch.object(gate.Path, "read_bytes", return_value=fragment):
            errors = gate.audit(GOOD.encode(), lock)
        self.assertTrue(any("CONFIG_KSU_SUSFS_SUS_PATH" in e for e in errors))

    def test_locked_fragment_hash_mismatch(self):
        from unittest.mock import patch
        lock = {"configuration": {**LOCK["configuration"],
                "fragment": "configs/ksun-susfs-6.1-features.config",
                "sha256": "0" * 64}}
        with patch.object(gate.Path, "read_bytes", return_value=b"wrong"):
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                gate.audit(GOOD.encode(), lock)

    def test_locked_fragment_subfeature_enabled(self):
        import hashlib
        from unittest.mock import patch
        fragment = b"CONFIG_KSU_SUSFS_SUS_PATH=y\n"
        lock = {"configuration": {**LOCK["configuration"],
                "fragment": "configs/ksun-susfs-6.1-features.config",
                "sha256": hashlib.sha256(fragment).hexdigest()}}
        with patch.object(gate.Path, "read_bytes", return_value=fragment):
            self.assertEqual([], gate.audit((GOOD + "CONFIG_KSU_SUSFS_SUS_PATH=y\n").encode(), lock))

    def test_locked_arm64_must_resolve_enabled(self):
        import hashlib
        from unittest.mock import patch
        fragment = b"CONFIG_ARM64=y\n"
        lock = {"configuration": {**LOCK["configuration"],
                "fragment": "configs/ksun-susfs-6.1-features.config",
                "sha256": hashlib.sha256(fragment).hexdigest()}}
        with patch.object(gate.Path, "read_bytes", return_value=fragment):
            errors = gate.audit(GOOD.encode(), lock)
        self.assertTrue(any("CONFIG_ARM64" in e for e in errors))

    def test_repository_lock_and_fragment_integrity(self):
        import hashlib
        import json
        lock_path = ROOT / "configs/ksun-susfs-6.1-features.lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        config = lock["configuration"]
        fragment = (ROOT / config["fragment"]).read_bytes()
        self.assertEqual(hashlib.sha256(fragment).hexdigest(), config["sha256"])
        self.assertEqual(config["target"], "gki_defconfig")
        self.assertTrue(config["fresh_output_required"])
        for guard in ("production_enabled", "run_full_build",
                      "release_allowed", "flash_allowed", "lkm_allowed"):
            self.assertIs(lock["guards"][guard], False)
        self.assertIn("CONFIG_KSU_SUSFS_SUS_PATH=y", fragment.decode())
        self.assertIn("# CONFIG_NTSYNC is not set", fragment.decode())

    def test_nomount_module_not_builtin(self):
        self.assertTrue(any("CONFIG_NOMOUNT" in error for error in
                            self.check(GOOD.replace("CONFIG_NOMOUNT=y", "CONFIG_NOMOUNT=m"))))


if __name__ == "__main__":
    unittest.main()
