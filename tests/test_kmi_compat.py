#!/usr/bin/env python3
"""Offline tests for the rothko KMI compatibility gate."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts import kmi_compat as kc

ROOT = Path(__file__).resolve().parents[1]
STG = """elf_symbol {
  id: 0x1
  name: "vendor_used"
  is_defined: true
  crc: 0x0000000a
}
elf_symbol {
  id: 0x2
  name: "changed_type"
  crc: 0x0000000b
}
elf_symbol {
  id: 0x3
  name: "no_crc"
}
"""


class KmiCompatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.src, self.out = base / "src", base / "out"
        (self.src / "android").mkdir(parents=True)
        (self.src / "kernel/module").mkdir(parents=True)
        self.out.mkdir()
        (self.src / "build.config.common").write_text("BRANCH=android14-6.1\nKMI_GENERATION=11\n")
        (self.src / "kernel/module/version.c").write_text(
            'pr_warn("%s: disagrees about version of symbol %s, but ignore...\\n", a, b);\n')
        (self.src / "android/abi_gki_aarch64").write_text("[abi_symbol_list]\n  vendor_used\n")
        (self.src / "android/abi_gki_aarch64_mtk").write_text("[abi_symbol_list]\n# comment\n  changed_type\n\n")
        (self.src / "android/abi_gki_aarch64_xiaomi").write_text("[abi_symbol_list]\n  xiaomi_only\n")
        (self.src / "android/abi_gki_aarch64.stg").write_text(STG)
        (self.out / "vmlinux.symvers").write_text(
            "0x0000000a\tvendor_used\tvmlinux\tEXPORT_SYMBOL\t\n"
            "0x000000ff\tchanged_type\tvmlinux\tEXPORT_SYMBOL_GPL\t\n"
            "0x00000001\txiaomi_only\tvmlinux\tEXPORT_SYMBOL\t\n")

    def run_gate(self):
        report_file = Path(self.temp.name) / "report.json"
        env_file = Path(self.temp.name) / "env"
        status = kc.main(["--device", "rothko", str(self.src), str(self.out),
                          "--json", str(report_file), "--github-env", str(env_file)])
        return status, json.loads(report_file.read_text()), env_file.read_text()

    def test_compatible_kernel_passes_and_reports_crc_differences(self):
        status, report, env = self.run_gate()
        self.assertEqual(status, 0, report)
        self.assertEqual(report["crc_differences"], ["changed_type"])
        self.assertEqual(report["lists"]["abi_gki_aarch64_mtk"], {"symbols": 1, "missing": []})
        self.assertIn("KMI_COMPAT=KMI Xiaomi 14T Pro (rothko): OK; generation 11", env)
        self.assertIn("mtk 1/1", env)
        self.assertIn("xiaomi 1/1", env)
        self.assertIn("CRC differs 1 (force-load on)", env)

    def test_missing_vendor_symbol_fails(self):
        (self.out / "vmlinux.symvers").write_text("0x0000000a\tvendor_used\tvmlinux\tEXPORT_SYMBOL\t\n")
        status, report, env = self.run_gate()
        self.assertEqual(status, 1)
        self.assertEqual(report["lists"]["abi_gki_aarch64_xiaomi"]["missing"], ["xiaomi_only"])
        self.assertIn("GAGAL / FAILED", env)

    def test_wrong_generation_protected_exports_and_no_force_load_fail(self):
        for change, message in (
                (lambda: (self.src / "build.config.common").write_text("KMI_GENERATION=8\n"), "KMI generation 8"),
                (lambda: (self.src / "android/abi_gki_protected_exports_aarch64").write_text("x\n"),
                 "protected exports still present"),
                (lambda: (self.src / "kernel/module/version.c").write_text("pr_warn(\"disagrees\");\n"),
                 "force-load change missing")):
            self.setUp()
            change()
            status, report, _ = self.run_gate()
            self.assertEqual(status, 1, message)
            self.assertTrue(any(message in error for error in report["errors"]), report["errors"])

    def test_symbols_exported_by_stock_gki_modules_are_accepted(self):
        (self.src / "android/abi_gki_aarch64_mtk").write_text("[abi_symbol_list]\n  changed_type\n  hci_cmd_sync_status\n")
        (self.src / "net/bluetooth").mkdir(parents=True)
        (self.src / "net/bluetooth/hci_sync.c").write_text("int hci_cmd_sync_status(void) {}\nEXPORT_SYMBOL(hci_cmd_sync_status);\n")
        status, report, _ = self.run_gate()
        self.assertEqual(status, 1)  # no GKI module list yet
        self.assertEqual(report["lists"]["abi_gki_aarch64_mtk"]["missing"], ["hci_cmd_sync_status"])
        (self.src / "modules.bzl").write_text('COMMON = [\n    "net/bluetooth/bluetooth.ko",\n]\n')
        status, report, env = self.run_gate()
        self.assertEqual(status, 0, report["errors"])
        self.assertEqual(report["from_gki_modules"], {"hci_cmd_sync_status": "net/bluetooth/bluetooth.ko"})
        self.assertIn("(1 via GKI modules)", env)
        # A GKI module elsewhere does not cover a symbol exported from another directory.
        (self.src / "modules.bzl").write_text('COMMON = ["lib/crypto/libarc4.ko"]\n')
        self.assertEqual(self.run_gate()[0], 1)

    def make_bsp(self, generation="11", mtk="changed_type", config="CONFIG_A=y\nCONFIG_MEDIA_CEC_RC=y\n"):
        bsp = Path(self.temp.name) / "bsp"
        (bsp / "android").mkdir(parents=True, exist_ok=True)
        (bsp / "arch/arm64/configs").mkdir(parents=True, exist_ok=True)
        (bsp / "build.config.common").write_text(f"KMI_GENERATION={generation}\n")
        (bsp / "android/abi_gki_aarch64").write_text("[abi_symbol_list]\n  vendor_used\n")
        (bsp / "android/abi_gki_aarch64_mtk").write_text(f"[abi_symbol_list]\n  {mtk}\n")
        (bsp / "android/abi_gki_aarch64_xiaomi").write_text("[abi_symbol_list]\n")
        (bsp / "arch/arm64/configs/gki_defconfig").write_text(config)
        (self.out / ".config").write_text("CONFIG_A=y\n# CONFIG_MEDIA_CEC_RC is not set\n")
        return bsp

    def run_reference(self, bsp):
        report_file = Path(self.temp.name) / "ref.json"
        status = kc.main(["--device", "rothko", str(self.src), str(self.out), "--reference", str(bsp),
                          "--json", str(report_file)])
        return status, json.loads(report_file.read_text())

    def test_bsp_reference_passes_with_reviewed_config_exceptions(self):
        status, report = self.run_reference(self.make_bsp())
        self.assertEqual(status, 0, report["errors"])
        self.assertEqual(report["reference"]["kmi_generation"], "11")
        self.assertEqual(report["reference"]["config_not_enabled"],
                         {"CONFIG_MEDIA_CEC_RC": kc.DEVICES["rothko"]["bsp_config_exceptions"]["CONFIG_MEDIA_CEC_RC"]})
        line = kc.summary(report)
        self.assertIn("BSP: generation 11, exported GKI 1/1, mtk 1/1, xiaomi 0/0, config =y not enabled 1 (reviewed)", line)

    def test_bsp_reference_failures(self):
        for change, message in (({"generation": "8"}, "BSP KMI generation 8"),
                                ({"mtk": "bsp_only_symbol"}, "BSP abi_gki_aarch64_mtk: 1 symbol(s) not exported"),
                                ({"config": "CONFIG_A=y\nCONFIG_INTERCONNECT=y\n"},
                                 "BSP gki_defconfig options not enabled: CONFIG_INTERCONNECT")):
            status, report = self.run_reference(self.make_bsp(**change))
            self.assertEqual(status, 1, message)
            self.assertTrue(any(message in error for error in report["errors"]), report["errors"])

    def test_bsp_only_vendor_hooks_fail_only_when_vendor_modules_use_them(self):
        bsp = self.make_bsp()
        (bsp / "include/trace/hooks").mkdir(parents=True)
        (bsp / "include/trace/hooks/pm_domain.h").write_text(
            "DECLARE_HOOK(android_vh_allow_domain_state,\n\tTP_PROTO(int a), TP_ARGS(a));\n"
            "DECLARE_RESTRICTED_HOOK(android_rvh_shared,\n\tTP_PROTO(int a), TP_ARGS(a), 1);\n")
        (self.src / "include/trace/hooks").mkdir(parents=True)
        (self.src / "include/trace/hooks/sched.h").write_text("DECLARE_RESTRICTED_HOOK(android_rvh_shared, x, y, 1);\n")
        status, report = self.run_reference(bsp)
        self.assertEqual(status, 0, report["errors"])
        self.assertEqual(report["reference"]["bsp_hooks_absent"],
                         {"android_vh_allow_domain_state": "unused by vendor modules"})
        (bsp / "android/abi_gki_aarch64_mtk").write_text(
            "[abi_symbol_list]\n  changed_type\n  __tracepoint_android_vh_allow_domain_state\n")
        status, report = self.run_reference(bsp)
        self.assertEqual(status, 1)
        self.assertTrue(any("BSP vendor hooks missing but used by vendor modules: android_vh_allow_domain_state" in e
                            for e in report["errors"]), report["errors"])

    def test_build_passes_the_bsp_reference_when_given(self):
        build = (ROOT / "build.sh").read_text()
        self.assertIn('[ -n "${ROTHKO_BSP_SRC:-}" ] && KMI_REFERENCE=(--reference "$ROTHKO_BSP_SRC")', build)
        self.assertIn('"$KSRC" "$OUTDIR" "${KMI_REFERENCE[@]}"', build)

    def test_module_symvers_is_the_fallback(self):
        (self.out / "vmlinux.symvers").rename(self.out / "Module.symvers")
        self.assertEqual(self.run_gate()[0], 0)

    def test_build_runs_the_gate_for_rothko_only(self):
        build = (ROOT / "build.sh").read_text()
        self.assertIn('scripts/kmi_compat.py" --device rothko "$KSRC" "$OUTDIR"', build)
        at = build.index('scripts/kmi_compat.py')
        self.assertIn('if [ "$TARGET_DEVICE" = "rothko" ]; then', build[at - 300:at])
        self.assertLess(build.index('echo "::group::[*] Building kernel"'), at)


if __name__ == "__main__":
    unittest.main()
