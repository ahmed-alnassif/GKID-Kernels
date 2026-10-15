#!/usr/bin/env python3
"""Brand the pinned AnyKernel3 (AK3-GKID) tree as Cogan, with upstream credits.

Rewrites, fail closed:
  anykernel.sh  kernel.string (shown by Kernel Flasher and recoveries), and the
                GKID support/community lines -> Cogan name and credits
  banner        GKID ASCII art -> Cogan ASCII art

The AnyKernel3 line "AnyKernel3 by osm0sis @ xda-developers" comes from
tools/ak3-core.sh and stays as it is.

Usage: brand_anykernel.py ANYKERNEL_DIR "KERNEL STRING"
"""
import re
import sys
from pathlib import Path

KERNEL_STRING = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._+()-]*")
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


def brand(script, kernel_string):
    if not KERNEL_STRING.fullmatch(kernel_string):
        raise ValueError(f"unsupported kernel string: {kernel_string!r}")
    lines = script.splitlines(keepends=True)
    names = [i for i, line in enumerate(lines) if line.startswith("kernel.string=")]
    if len(names) != 1:
        raise ValueError(f"expected one kernel.string line, found {len(names)}")
    lines[names[0]] = f"kernel.string={kernel_string}\n"
    starts = [i for i, line in enumerate(lines) if "GKID Supported" in line]
    ends = [i for i, line in enumerate(lines) if "t.me/" in line]
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        raise ValueError("GKID support/community block not found in anykernel.sh")
    lines[starts[0]:ends[0] + 1] = BLOCK
    result = "".join(lines)
    credits = set(BLOCK)
    leftover = [line.strip() for line in result.splitlines(keepends=True)
                if line not in credits and any(marker in line for marker in UPSTREAM_MARKERS)]
    if leftover:
        raise ValueError("upstream branding left in anykernel.sh: " + "; ".join(leftover))
    if "$kernel_supported || abort" not in result:
        raise ValueError("device check line missing after branding")
    return result


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(argv[1])
    try:
        script = root / "anykernel.sh"
        script.write_text(brand(script.read_text(encoding="utf-8"), argv[2]), encoding="utf-8")
        (root / "banner").write_text(BANNER, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("BLOCKED: AnyKernel3 branding: " + str(exc), file=sys.stderr)
        return 1
    print(f"AnyKernel3 branded: kernel.string={argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
