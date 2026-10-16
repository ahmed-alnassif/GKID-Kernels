#!/usr/bin/env python3
"""Describe what a finished Cogan kernel build really contains.

Reads the resolved O=/.config and the kernel source tree, never the form inputs,
so the line cannot claim a feature the build lacks:
  SUSFS            CONFIG_KSU_SUSFS=y
  BBRv3 / BBR      CONFIG_TCP_CONG_BBR=y; v3 when net/ipv4/tcp_bbr.c defines
                   BBR_VERSION 3 (the BBRv3 patch), "(default)" when it is the
                   default congestion control
  BBG, NoMount     CONFIG_BBG=y, CONFIG_NOMOUNT=y
  LTO              Full / Thin / No LTO

Prints one line such as "SUSFS, BBRv3 (default), BBG, NoMount, Full LTO".

Usage: kernel_features.py CONFIG KERNEL_SOURCE [--github-env FILE]
"""
import argparse
import re
import sys
from pathlib import Path

BBR_V3 = re.compile(r"^#define\s+BBR_VERSION\s+3\b", re.MULTILINE)


def read_config(text):
    values = {}
    for line in text.splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            values[line[2:-11]] = "n"
    return values


def features(config_text, bbr_source=""):
    config = read_config(config_text)
    on = lambda key: config.get(key) == "y"  # noqa: E731
    found = []
    if on("CONFIG_KSU_SUSFS"):
        found.append("SUSFS")
    if on("CONFIG_TCP_CONG_BBR"):
        name = "BBRv3" if BBR_V3.search(bbr_source) else "BBR"
        found.append(name + (" (default)" if config.get("CONFIG_DEFAULT_TCP_CONG") == '"bbr"' else ""))
    if on("CONFIG_BBG"):
        found.append("BBG")
    if on("CONFIG_NOMOUNT"):
        found.append("NoMount")
    if on("CONFIG_LTO_CLANG_FULL"):
        found.append("Full LTO")
    elif on("CONFIG_LTO_CLANG_THIN"):
        found.append("Thin LTO")
    else:
        found.append("No LTO")
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("--github-env")
    args = parser.parse_args(argv)
    try:
        config_text = args.config.read_text(encoding="utf-8")
        bbr = args.source / "net/ipv4/tcp_bbr.c"
        bbr_source = bbr.read_text(encoding="utf-8", errors="replace") if bbr.is_file() else ""
    except OSError as exc:
        print("kernel features unreadable: " + str(exc), file=sys.stderr)
        return 1
    line = ", ".join(features(config_text, bbr_source))
    print(line)
    if args.github_env:
        with open(args.github_env, "a", encoding="utf-8") as handle:
            handle.write(f"KERNEL_FEATURES={line}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
