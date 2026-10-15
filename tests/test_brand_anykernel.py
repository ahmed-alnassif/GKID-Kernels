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

    def test_main_rewrites_script_and_banner(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            shutil.copy(FIXTURES / "ak3-gkid-anykernel.sh", directory / "anykernel.sh")
            shutil.copy(FIXTURES / "ak3-gkid-banner", directory / "banner")
            self.assertEqual(ba.main(["brand", str(directory), STRING]), 0)
            self.assertEqual((directory / "banner").read_text(), ba.BANNER)
            self.assertIn(STRING, (directory / "anykernel.sh").read_text())

    def test_build_uses_the_branding_script_not_the_old_sed(self):
        build = (ROOT / "build.sh").read_text()
        self.assertIn('scripts/brand_anykernel.py" "$WORKDIR/anykernel"', build)
        self.assertNotIn("by Ahmed Al-Nassif (ahmed-alnassif)", build)


if __name__ == "__main__":
    unittest.main()
