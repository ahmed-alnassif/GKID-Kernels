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

    def test_disabled_fragment_flag_cannot_be_enabled(self):
        import hashlib
        from unittest.mock import patch
        fragment = b"# CONFIG_NTSYNC is not set\n"
        lock = {"configuration": {**LOCK["configuration"],
                "fragment": "configs/ksun-susfs-6.1-features.config",
                "sha256": hashlib.sha256(fragment).hexdigest()}}
        with patch.object(gate.Path, "read_bytes", return_value=fragment):
            errors = gate.audit(GOOD.replace("# CONFIG_NTSYNC is not set",
                                             "CONFIG_NTSYNC=y").encode(), lock)
        self.assertTrue(any("disabled in locked fragment" in e for e in errors))

    def test_locked_lsm_list_cannot_drop_selinux(self):
        import hashlib
        from unittest.mock import patch
        fragment = b'CONFIG_LSM="landlock,selinux,baseband_guard"\n'
        lock = {"configuration": {**LOCK["configuration"],
                "fragment": "configs/ksun-susfs-6.1-features.config",
                "sha256": hashlib.sha256(fragment).hexdigest()}}
        reduced = GOOD.replace("landlock,selinux,baseband_guard",
                               "landlock,baseband_guard")
        with patch.object(gate.Path, "read_bytes", return_value=fragment):
            errors = gate.audit(reduced.encode(), lock)
        self.assertTrue(any("resolved list differs" in e for e in errors))

    def test_unquoted_lsm_is_rejected(self):
        errors = self.check(GOOD.replace('CONFIG_LSM="landlock,selinux,baseband_guard"',
                                         "CONFIG_LSM=landlock,selinux,baseband_guard"))
        self.assertTrue(any("quoted Kconfig string" in e for e in errors))

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

    def test_cli_rejects_enabled_production_guard(self):
        import json
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".config"
            config_path.write_text(GOOD, encoding="utf-8")
            lock_path = Path(tmp) / "lock.json"
            lock_path.write_text(json.dumps({
                "configuration": {"target": "gki_defconfig", **LOCK["configuration"]},
                "guards": {
                    "production_enabled": True,
                    "run_full_build": False,
                    "release_allowed": False,
                    "flash_allowed": False,
                    "lkm_allowed": False,
                },
            }), encoding="utf-8")
            with patch.object(gate, "LOCK", lock_path), patch.object(
                    gate.sys, "argv", ["gate", str(config_path)]):
                self.assertEqual(1, gate.main())

    def test_bbg_recovery_partition_protection_forbidden(self):
        lock = {"configuration": {**LOCK["configuration"],
                "forbidden": [*LOCK["configuration"]["forbidden"],
                              "CONFIG_BBG_BLOCK_RECOVERY"]}}
        errors = gate.audit((GOOD + "CONFIG_BBG_BLOCK_RECOVERY=y\n").encode(), lock)
        self.assertTrue(any("CONFIG_BBG_BLOCK_RECOVERY" in e for e in errors))

    def test_malformed_config_assignment_rejected(self):
        with self.assertRaisesRegex(ValueError, "Malformed config entry"):
            self.check(GOOD + "CONFIG_BBG =n\n")

    def test_malformed_disabled_config_rejected(self):
        with self.assertRaisesRegex(ValueError, "Malformed config entry"):
            self.check(GOOD + "# CONFIG_NTSYNC is not set \n")

    def test_lowercase_kconfig_symbols_accepted(self):
        self.assertEqual(self.check(GOOD + "CONFIG_FONT_8x16=y\n"
                                    "# CONFIG_SCSI_DC395x is not set\n"), [])

    def test_malformed_disabled_symbol_rejected(self):
        with self.assertRaisesRegex(ValueError, "Malformed config entry"):
            self.check(GOOD + "# CONFIG_BAD-NAME is not set\n")

    def test_repository_lock_forbids_samsung_ksu_options(self):
        # Bootloop on a MediaTek GKI device: Samsung KDP init failed, ksu_cred stayed
        # NULL and the SUSFS init.rc hook crashed in override_creds().
        import json
        lock = json.loads((ROOT / "configs/ksun-susfs-6.1-features.lock.json")
                          .read_text(encoding="utf-8"))
        fragment = (ROOT / lock["configuration"]["fragment"]).read_text(encoding="utf-8")
        for key in ("CONFIG_KSU_SAMSUNG_KDP", "CONFIG_KSU_SAMSUNG_RKP",
                    "CONFIG_KSU_SAMSUNG_DEFEX"):
            self.assertIn(key, lock["configuration"]["forbidden"])
            self.assertIn(f"# {key} is not set", fragment.splitlines())
            errors = gate.audit((GOOD + f"{key}=y\n").encode(), lock)
            self.assertTrue(any(key in e for e in errors))

    def test_repository_candidate_carries_production_bbrv3_and_networking(self):
        import hashlib
        import json
        lock = json.loads((ROOT / "configs/ksun-susfs-6.1-features.lock.json").read_text(encoding="utf-8"))
        features = ROOT / "kernel-patches/susfs/6.1-v2/features"
        patch = (features / "004-bbrv3.patch").read_bytes()
        # Byte-identical to the BBRv3 patch the other variants apply, applied last.
        self.assertEqual(patch, (ROOT / "kernel-patches/bbrv3/bbrv3.patch").read_bytes())
        digest = hashlib.sha256(patch).hexdigest()
        replay = json.loads((features / "kernel-replay.json").read_text(encoding="utf-8"))
        self.assertEqual(replay["patches"][-2], {"path": "004-bbrv3.patch", "sha256": digest})
        # The bbr3 name patch (005) is the production bbr3-alias.patch, applied right after.
        alias = (features / "005-bbr3-alias.patch").read_bytes()
        self.assertEqual(alias, (ROOT / "kernel-patches/bbrv3/bbr3-alias.patch").read_bytes())
        self.assertEqual(replay["patches"][-1],
                         {"path": "005-bbr3-alias.patch", "sha256": hashlib.sha256(alias).hexdigest()})
        self.assertEqual(lock["reviewed_patches"][-1]["applies_after"], "004-bbrv3.patch")
        build = (ROOT / "build.sh").read_text(encoding="utf-8")
        # Fail closed: the fuzz fallback cannot dry-run this multi-commit series.
        self.assertIn('apply_patch_file "$KERNEL_PATCHES/bbrv3/bbrv3.patch" || { error "BBRv3 patch failed (Networking enabled)"; exit 1; }',
                      build)
        self.assertIn('apply_patch_file "$KERNEL_PATCHES/bbrv3/bbr3-alias.patch" || {', build)
        reviewed = {item["name"]: item for item in lock["reviewed_patches"]}
        self.assertEqual(reviewed["004-bbrv3.patch"]["sha256"], digest)
        self.assertNotEqual(lock["integrated_kernel_tree"], lock["integrated_kernel_tree_before_bbrv3"])
        # Same networking extras as configs/custom.config, and the gate requires BBR.
        fragment = (ROOT / lock["configuration"]["fragment"]).read_text(encoding="utf-8")
        custom = (ROOT / "configs/custom.config").read_text(encoding="utf-8")
        extras = custom[custom.index("# Networking extras\n"):].splitlines()[1:]
        for line in extras:
            if line.startswith("CONFIG_"):
                self.assertIn(line + "\n", fragment)
        for key in ("CONFIG_TCP_CONG_BBR", "CONFIG_DEFAULT_BBR", "CONFIG_NET_SCH_FQ"):
            self.assertEqual(lock["configuration"]["required"][key], "y")
        self.assertEqual(hashlib.sha256((ROOT / lock["configuration"]["fragment"]).read_bytes()).hexdigest(),
                         lock["configuration"]["sha256"])

    def test_nomount_module_not_builtin(self):
        self.assertTrue(any("CONFIG_NOMOUNT" in error for error in
                            self.check(GOOD.replace("CONFIG_NOMOUNT=y", "CONFIG_NOMOUNT=m"))))


if __name__ == "__main__":
    unittest.main()
