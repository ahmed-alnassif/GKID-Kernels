#!/usr/bin/env python3
"""Offline tests for brand_anykernel.py against a copy of the pinned AK3-GKID files."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import brand_anykernel as ba

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
PINNED = (FIXTURES / "ak3-gkid-anykernel.sh").read_text(encoding="utf-8")
STRING = "Cogan v26.10.16-r14 6.1.177 KernelSU+SuSFS by Cogan (cogan17)"


class BrandTests(unittest.TestCase):
    def test_pinned_script_gets_cogan_name_and_credits(self):
        result = ba.brand(PINNED, STRING)
        self.assertIn(f"kernel.string={STRING}\n", result)
        self.assertNotIn("Telegram", result)
        self.assertNotIn("Thank you for using GKID", result)
        self.assertIn('ui_print " " "Cogan Kernel by Cogan (cogan17)"', result)
        self.assertIn('ui_print "- GKID/Duchamp: Ahmed Al-Nassif"', result)
        self.assertIn('ui_print "- AnyKernel3: osm0sis"', result)
        # Everything else (device check, flashing) is untouched.
        self.assertIn("$kernel_supported || abort", result)
        for line in ("block=boot", "split_boot", "flash_boot", "write_boot", ". tools/ak3-core.sh"):
            self.assertIn(line, result)
        self.assertTrue(all(len(line) <= 32 for line in ba.CREDITS))

    def test_features_line_follows_the_cogan_name(self):
        features = "SUSFS, BBRv3 (default), BBG, NoMount, Full LTO"
        result = ba.brand(PINNED, STRING, features)
        self.assertIn('ui_print "github.com/cogan17/Cogan"\nui_print "Features: ' + features + '"\n', result)
        self.assertNotIn("Features:", ba.brand(PINNED, STRING))
        with tempfile.NamedTemporaryFile("w", suffix=".sh") as handle:
            handle.write(result)
            handle.flush()
            self.assertEqual(subprocess.run(["bash", "-n", handle.name]).returncode, 0)
        for bad in ('SUSFS"; reboot', "BBRv3 $(id)", "SUSFS`id`"):
            with self.assertRaisesRegex(ValueError, "features"):
                ba.brand(PINNED, STRING, bad)

    def test_branded_script_is_valid_shell(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sh") as handle:
            handle.write(ba.brand(PINNED, STRING))
            handle.flush()
            self.assertEqual(subprocess.run(["bash", "-n", handle.name]).returncode, 0)

    def test_changed_upstream_layout_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "block not found"):
            ba.brand(PINNED.replace("GKID Supported", "Supported"), STRING)
        with self.assertRaisesRegex(ValueError, "one kernel.string"):
            ba.brand(PINNED.replace("kernel.string=", "kernel.name="), STRING)
        with self.assertRaisesRegex(ValueError, "branding left"):
            ba.brand(PINNED + 'ui_print "Join GKID community"\n', STRING)
        with self.assertRaisesRegex(ValueError, "unsupported kernel string"):
            ba.brand(PINNED, "Cogan' ; reboot")

    def test_rothko_build_flashes_only_on_rothko(self):
        result = ba.brand(PINNED, STRING.replace("Cogan ", "Cogan-Rothko "), "SUSFS", "rothko")
        self.assertIn("do.devicecheck=1\n", result)
        self.assertIn("device.name1=rothko\n", result)
        self.assertIn("device.name2=\n", result)
        self.assertIn('ui_print "Device: Xiaomi 14T Pro (rothko)"\n', result)
        self.assertLess(result.index("Features: SUSFS"), result.index("Device: Xiaomi"))
        generic = ba.brand(PINNED, STRING)
        self.assertIn("do.devicecheck=0\n", generic)
        self.assertNotIn("Device:", generic)
        with self.assertRaisesRegex(ValueError, "unsupported device"):
            ba.brand(PINNED, STRING, "", "poco")
        with self.assertRaisesRegex(ValueError, "expected one do.devicecheck"):
            ba.brand(PINNED.replace("do.devicecheck=0\n", ""), STRING, "", "rothko")
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            shutil.copy(FIXTURES / "ak3-gkid-anykernel.sh", directory / "anykernel.sh")
            shutil.copy(FIXTURES / "ak3-gkid-banner", directory / "banner")
            self.assertEqual(ba.main(["brand", str(directory), STRING, "SUSFS", "--device", "rothko"]), 0)
            self.assertIn("device.name1=rothko", (directory / "anykernel.sh").read_text())
            self.assertEqual(ba.main(["brand", str(directory), STRING, "--device"]), 2)

    def test_main_rewrites_script_and_banner(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            shutil.copy(FIXTURES / "ak3-gkid-anykernel.sh", directory / "anykernel.sh")
            shutil.copy(FIXTURES / "ak3-gkid-banner", directory / "banner")
            self.assertEqual(ba.main(["brand", str(directory), STRING]), 0)
            self.assertEqual((directory / "banner").read_text(), ba.BANNER)
            self.assertIn(STRING, (directory / "anykernel.sh").read_text())

    def test_build_passes_the_detected_features_to_the_banner(self):
        build = (ROOT / "build.sh").read_text(encoding="utf-8")
        self.assertIn('scripts/kernel_features.py" "$OUTDIR/.config" "$KSRC"', build)
        self.assertIn('by Cogan (cogan17)" "$KERNEL_FEATURES" "${BRAND_ARGS[@]}" || exit 1', build)

    def test_build_uses_the_branding_script_not_the_old_sed(self):
        build = (ROOT / "build.sh").read_text()
        self.assertIn('scripts/brand_anykernel.py" "$WORKDIR/anykernel"', build)
        self.assertNotIn("by Ahmed Al-Nassif (ahmed-alnassif)", build)


if __name__ == "__main__":
    unittest.main()
