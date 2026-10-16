#!/usr/bin/env python3
"""Fetch the ACK source of a device's stock kernel for the KMI gate (kmi_compat.py).

Only what the gate reads, at the pinned commit of kmi_compat.DEVICES[device]["stock"]:
android/ (symbol lists, frozen ABI), arch/arm64/configs/, build.config.common,
include/trace/hooks/, Makefile and modules.bzl - a sparse, shallow, blob-less fetch of
about 10 MB. Fails unless HEAD is the pinned commit and the Makefile is the stock version.

Usage: stock_reference.py --device rothko DEST
       stock_reference.py --device rothko --pin   (prints: REPOSITORY COMMIT VERSION)
The same pin is the kernel source of KERNEL_SOURCE=stock builds (build.sh).
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kmi_compat import DEVICES, kernel_version  # noqa: E402

PATHS = ["/android/", "/arch/arm64/configs/", "/build.config.common", "/include/trace/hooks/",
         "/Makefile", "/modules.bzl"]


def git(dest, *args):
    subprocess.run(["git", "-C", str(dest), *args], check=True)


def fetch(device, dest, repo=None):
    stock = DEVICES[device]["stock"]
    if dest.exists() and any(dest.iterdir()):
        raise ValueError(f"{dest} is not empty")
    dest.mkdir(parents=True, exist_ok=True)
    git(dest, "init", "-q")
    git(dest, "remote", "add", "origin", repo or stock["repo"])
    git(dest, "sparse-checkout", "set", "--no-cone", *PATHS)
    git(dest, "fetch", "-q", "--depth=1", "--filter=blob:none", "origin", stock["commit"])
    git(dest, "checkout", "-q", "FETCH_HEAD")
    head = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    if head != stock["commit"]:
        raise ValueError(f"fetched {head}, the pinned stock commit is {stock['commit']}")
    if kernel_version(dest) != stock["version"]:
        raise ValueError(f"fetched kernel {kernel_version(dest)}, the stock kernel is {stock['version']}")
    return stock


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", required=True, choices=sorted(d for d in DEVICES if "stock" in DEVICES[d]))
    parser.add_argument("dest", type=Path, nargs="?")
    parser.add_argument("--repo", help="override the source repository (a local mirror for tests)")
    parser.add_argument("--pin", action="store_true", help="print the pinned repository, commit and version")
    args = parser.parse_args(argv)
    if args.pin:
        stock = DEVICES[args.device]["stock"]
        print(stock["repo"], stock["commit"], stock["version"])
        return 0
    if args.dest is None:
        parser.error("DEST is required unless --pin is given")
    try:
        stock = fetch(args.device, args.dest, args.repo)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"BLOCKED: stock kernel reference: {exc}", file=sys.stderr)
        return 1
    print(f"Stock kernel reference: {stock['kernel']} ({stock['tag']}, {stock['commit'][:12]}) in {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
