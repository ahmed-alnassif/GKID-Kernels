#!/usr/bin/env python3
"""Stage the validated KSUN + SUSFS 6.1 candidate for a build (fail closed).

Reproduces exactly what was verified offline and built locally:
  kernel @ locked sublevel commit -> core replay (driver glue, SUSFS, companions)
  KSUN fork @ manifest commit     -> offline version metadata
  frozen core snapshots (deterministic commit-tree, metadata from the lock)
  feature replay (BBG, NoMount, BBG allow-cache fix, BBRv3 + bbr3 name) -> expected index tree
  GKID-equivalent stack (gkid_parity.py) on plain android14-6.1-lts sublevels -> final tree

Usage: python3 scripts/stage_ksun_susfs_candidate.py KERNEL_DIR KSUN_DIR [SUBLEVEL]
SUBLEVEL is one of "sublevels" in the feature lock (default: 177, the
device-tested kernel of the replay manifest); every tree of that sublevel is
checked. KERNEL_DIR must be a clean checkout of that sublevel's commit; KSUN_DIR
must not exist and must be the sibling that drivers/kernelsu points to.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gkid_parity  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "kernel-patches/susfs/6.1-v2"
FEATURE_LOCK = ROOT / "configs/ksun-susfs-6.1-features.lock.json"
SOURCE_LOCK = ROOT / "configs/ksun-susfs-6.1-v2.lock.json"
REPLAY = ROOT / "scripts/ksun_susfs_replay.py"


def git(repo, *args, env=None):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                            text=True, env=env, timeout=600)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()[:500]}")
    return result.stdout.strip()


def replay(tree, manifest, head=None):
    command = [sys.executable, str(REPLAY), str(tree), str(manifest), "--apply"]
    if head:
        command += ["--kernel-commit", head]
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    print(result.stdout, end="")
    if result.returncode:
        raise RuntimeError(f"Replay {manifest.name} failed: {result.stderr.strip()[:1000]}")


def expect(label, actual, expected):
    if actual != expected:
        raise RuntimeError(f"{label}: got {actual}, expected {expected}")
    print(f"[+] {label}: {actual}")


def freeze(repo, core_tree, parent, snapshot, meta):
    """Stage everything, then commit-tree with the recorded fixed identity."""
    git(repo, "add", "-A")
    expect(f"{repo.name} core tree", git(repo, "write-tree"), core_tree)
    env = {**os.environ,
           "GIT_AUTHOR_NAME": meta["author_name"], "GIT_AUTHOR_EMAIL": meta["author_email"],
           "GIT_AUTHOR_DATE": meta["author_date"], "GIT_COMMITTER_NAME": meta["committer_name"],
           "GIT_COMMITTER_EMAIL": meta["committer_email"], "GIT_COMMITTER_DATE": meta["committer_date"]}
    result = subprocess.run(["git", "-C", str(repo), "commit-tree", core_tree, "-p", parent],
                            input=meta["message"], capture_output=True, text=True, env=env, timeout=60)
    if result.returncode:
        raise RuntimeError("commit-tree failed: " + result.stderr.strip())
    expect(f"{repo.name} frozen snapshot", result.stdout.strip(), snapshot)
    git(repo, "reset", "-q", "--soft", snapshot)
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError(f"{repo.name} not clean after freezing")


def main(argv):
    if len(argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    kernel, ksun = Path(argv[1]).resolve(), Path(argv[2]).absolute()
    try:
        lock = json.loads(FEATURE_LOCK.read_text())
        sources = json.loads(SOURCE_LOCK.read_text())
        ksun_manifest = json.loads((BASE / "replay/ksun-replay.json").read_text())
        meta = lock["frozen_core"]
        sublevel = argv[3] if len(argv) == 4 else "177"
        if sublevel not in lock["sublevels"]:
            raise RuntimeError(f"KSUN+SUSFS is not verified for 6.1.{sublevel}; "
                               f"available: {', '.join(sorted(lock['sublevels'], key=int))}")
        target = lock["sublevels"][sublevel]
        print(f"[+] KSUN+SUSFS sublevel 6.1.{sublevel}")

        expect("kernel checkout", git(kernel, "rev-parse", "HEAD"), target["kernel_commit"])
        if ksun.exists():
            raise RuntimeError(f"{ksun} already exists")
        if ksun.parent != kernel.parent:
            raise RuntimeError("KSUN must be a sibling of the kernel checkout (drivers/kernelsu -> ../../ksun/kernel)")

        ksun.mkdir()
        git(ksun, "init", "-q")
        git(ksun, "fetch", "-q", "--depth=1", sources["sources"]["ksun"]["repository"],
            ksun_manifest["kernel_commit"])
        git(ksun, "checkout", "-q", "--detach", "FETCH_HEAD")
        expect("KSUN checkout", git(ksun, "rev-parse", "HEAD"), ksun_manifest["kernel_commit"])

        replay(kernel, BASE / "replay/kernel-replay.json", target["kernel_commit"])
        replay(ksun, BASE / "replay/ksun-replay.json")
        freeze(kernel, target["core_kernel_tree"], target["kernel_commit"], target["kernel_snapshot"], meta)
        freeze(ksun, lock["core_ksun_tree"], ksun_manifest["kernel_commit"], meta["ksun_snapshot"], meta)

        replay(kernel, BASE / "features/kernel-replay.json", target["kernel_snapshot"])
        git(kernel, "add", "-A")
        expect("feature tree", git(kernel, "write-tree"), target["integrated_kernel_tree"])

        stack = gkid_parity.has_stack((kernel / gkid_parity.VERSION_C).read_text(errors="replace"))
        if stack != target["gkid_stack"]:
            raise RuntimeError(f"GKID patch stack present={stack}, lock says {target['gkid_stack']}")
        if not stack:
            removed = gkid_parity.apply(kernel)
            print(f"[+] GKID-equivalent stack applied ({len(gkid_parity.patches())} patches, "
                  f"removed {', '.join(removed)})")
            git(kernel, "add", "-A")
        expect("final tree", git(kernel, "write-tree"), target["final_kernel_tree"])
        print("CANDIDATE STAGED: KSUN + SUSFS 6.1 with BBG (001, 003), NoMount (002) and BBRv3 (004, bbr3 name 005)")
        return 0
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + str(exc)[:2000], file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
