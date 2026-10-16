#!/usr/bin/env python3
"""Brand the pinned AnyKernel3 (AK3-GKID) tree as Cogan, with upstream credits.

Rewrites, fail closed:
  anykernel.sh  kernel.string (shown by Kernel Flasher and recoveries), and the
                GKID support/community lines -> Cogan name and credits
  banner        GKID ASCII art -> Cogan ASCII art

The AnyKernel3 line "AnyKernel3 by osm0sis @ xda-developers" comes from
tools/ak3-core.sh and stays as it is. An optional FEATURES line (from
kernel_features.py, i.e. the built config) is shown under the Cogan name.

--device CODENAME (only rothko, the Xiaomi 14T Pro) turns on the AnyKernel3
device check: the ZIP aborts unless ro.product.device / ro.build.product (or
their vendor variants) equal the codename.

Usage: brand_anykernel.py ANYKERNEL_DIR "KERNEL STRING" ["FEATURES"] [--device CODENAME]
"""
import re
import sys
from pathlib import Path

KERNEL_STRING = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._+()-]*")
FEATURES = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ,._+()-]*")
BANNER = r"""  ___
 / __|___  __ _ __ _ _ _
| (__/ _ \/ _` / _` | ' \
 \___\___/\__, \__,_|_||_|
          |___/
"""
# Short lines: Kernel Flasher wraps at about 32 characters.
CREDITS = [
    "- GKID/Duchamp: Ahmed Al-Nassif",
    "- KernelSU: tiann",
    "- KernelSU Next: rifsxd",
    "- KSUN SUSFS fork: pershoot",
    "- BakaSU: Baka-SU",
    "- SUSFS: simonpunk",
    "- NoMount: maxsteeel",
    "- Baseband Guard: vc-teahouse",
    "- AnyKernel3: osm0sis",
]
BLOCK = [
    'ui_print " " "  -> Kernel 6.1 supported: $kernel_supported"\n',
    'ui_print " " "Cogan Kernel by Cogan (cogan17)"\n',
    'ui_print "github.com/cogan17/Cogan"\n',
    'ui_print " " "Credits:"\n',
    *[f'ui_print "{line}"\n' for line in CREDITS],
    'ui_print " "\n',
]
UPSTREAM_MARKERS = ("GKID", "t.me/", "Telegram", "Thank you for using", "community")
# Codename -> name shown while flashing. AnyKernel3 compares the codename with
# ro.product.device, ro.build.product, ro.product.vendor.device, ro.vendor.product.device.
DEVICES = {"rothko": "Xiaomi 14T Pro (rothko)"}


def block(features="", device=None):
    extra = []
    if features:
        if not FEATURES.fullmatch(features):
            raise ValueError(f"unsupported features line: {features!r}")
        extra.append(f'ui_print "Features: {features}"\n')
    if device:
        extra.append(f'ui_print "Device: {DEVICES[device]}"\n')
    at = BLOCK.index('ui_print "github.com/cogan17/Cogan"\n') + 1
    return [*BLOCK[:at], *extra, *BLOCK[at:]]


def set_property(lines, key, value):
    found = [i for i, line in enumerate(lines) if line.startswith(key + "=")]
    if len(found) != 1:
        raise ValueError(f"expected one {key} line, found {len(found)}")
    lines[found[0]] = f"{key}={value}\n"


def brand(script, kernel_string, features="", device=None):
    if not KERNEL_STRING.fullmatch(kernel_string):
        raise ValueError(f"unsupported kernel string: {kernel_string!r}")
    if device is not None and device not in DEVICES:
        raise ValueError(f"unsupported device: {device!r}")
    lines_to_insert = block(features, device)
    lines = script.splitlines(keepends=True)
    if device:
        # Device-specific build: AnyKernel3 refuses to flash it on any other phone.
        set_property(lines, "do.devicecheck", "1")
        set_property(lines, "device.name1", device)
    names = [i for i, line in enumerate(lines) if line.startswith("kernel.string=")]
    if len(names) != 1:
        raise ValueError(f"expected one kernel.string line, found {len(names)}")
    lines[names[0]] = f"kernel.string={kernel_string}\n"
    starts = [i for i, line in enumerate(lines) if "GKID Supported" in line]
    ends = [i for i, line in enumerate(lines) if "t.me/" in line]
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        raise ValueError("GKID support/community block not found in anykernel.sh")
    lines[starts[0]:ends[0] + 1] = lines_to_insert
    result = "".join(lines)
    credits = set(lines_to_insert)
    leftover = [line.strip() for line in result.splitlines(keepends=True)
                if line not in credits and any(marker in line for marker in UPSTREAM_MARKERS)]
    if leftover:
        raise ValueError("upstream branding left in anykernel.sh: " + "; ".join(leftover))
    if "$kernel_supported || abort" not in result:
        raise ValueError("device check line missing after branding")
    return result


def main(argv):
    argv, device = list(argv), None
    if "--device" in argv:
        at = argv.index("--device")
        if at + 1 >= len(argv):
            print(__doc__, file=sys.stderr)
            return 2
        device = argv[at + 1]
        del argv[at:at + 2]
    if len(argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(argv[1])
    features = argv[3] if len(argv) == 4 else ""
    try:
        script = root / "anykernel.sh"
        script.write_text(brand(script.read_text(encoding="utf-8"), argv[2], features, device),
                          encoding="utf-8")
        (root / "banner").write_text(BANNER, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("BLOCKED: AnyKernel3 branding: " + str(exc), file=sys.stderr)
        return 1
    print(f"AnyKernel3 branded: kernel.string={argv[2]}" + (f"; features: {features}" if features else "")
          + (f"; device check: {device}" if device else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
