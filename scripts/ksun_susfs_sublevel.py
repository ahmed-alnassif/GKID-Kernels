#!/usr/bin/env python3
"""Kernel sublevels of the KSUN + SUSFS build (offline, fail closed).

Usage:
  ksun_susfs_sublevel.py resolve SUBLEVEL
      Print the sublevel KSUN + SUSFS builds for the form value SUBLEVEL:
      lts/auto/empty = the newest verified one, a number = that one if verified.
  ksun_susfs_sublevel.py record KERNEL_REPO COMMIT
      Compute the locked identities of one GKID 6.1 commit.

record: KERNEL_REPO is any Git repository that already holds COMMIT (for example a
`git fetch --depth=1` of the pinned sublevel); its work tree, index and refs are
not touched. The same checksum-verified series that stage_ksun_susfs_candidate.py
replays (core 001-003, frozen snapshot, features 001-005, then the GKID-equivalent
stack of gkid_parity.py when the commit is plain android14-6.1-lts) is applied
strictly, without fuzz, to a disposable index. On success it prints the JSON entry to add
under "sublevels" in configs/ksun-susfs-6.1-features.lock.json; the build then
accepts that sublevel for KSUN + SUSFS and checks the same trees again.

A sublevel whose context differs fails here and stays unavailable: the patches
are never adapted automatically.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gkid_parity  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "kernel-patches/susfs/6.1-v2"
FEATURE_LOCK = ROOT / "configs/ksun-susfs-6.1-features.lock.json"
MANIFESTS = (BASE / "replay/kernel-replay.json", BASE / "features/kernel-replay.json")
SHA = re.compile(r"[0-9a-f]{40}")


def git(repo, *args, env=None, data=None):
    result = subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True,
                            env=env, timeout=600)
    if result.returncode:
        raise RuntimeError(f"git {args[0]} failed: "
                           + result.stderr.decode(errors="replace").strip()[:1500])
    return result.stdout.decode().strip()


def series(manifest):
    """Patch bytes of a replay manifest, each checked against its SHA256."""
    data = json.loads(manifest.read_text(encoding="utf-8"))
    patches = []
    for entry in data["patches"]:
        raw = (manifest.parent / entry["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"checksum mismatch: {entry['path']}")
        patches.append((entry["path"], raw))
    return patches


def identities(repo, commit, lock):
    if not SHA.fullmatch(commit):
        raise ValueError("COMMIT must be a full 40-character SHA")
    makefile = git(repo, "show", f"{commit}:Makefile")
    fields = dict(re.findall(r"^(VERSION|PATCHLEVEL|SUBLEVEL) = (\d+)$", makefile, re.MULTILINE))
    if (fields.get("VERSION"), fields.get("PATCHLEVEL")) != ("6", "1") or "SUBLEVEL" not in fields:
        raise ValueError("COMMIT is not a 6.1 kernel")
    meta = lock["frozen_core"]
    core, features = (series(manifest) for manifest in MANIFESTS)
    with tempfile.TemporaryDirectory(prefix="ksun-susfs-sublevel-") as temp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp) / "index"))
        git(repo, "read-tree", commit, env=env)

        def apply(patches):
            for name, raw in patches:
                try:
                    git(repo, "apply", "--cached", "-", env=env, data=raw)
                except RuntimeError as exc:
                    raise RuntimeError(f"{name} does not apply: {exc}") from None
            return git(repo, "write-tree", env=env)

        core_tree = apply(core)
        frozen = dict(env, GIT_AUTHOR_NAME=meta["author_name"], GIT_AUTHOR_EMAIL=meta["author_email"],
                      GIT_AUTHOR_DATE=meta["author_date"], GIT_COMMITTER_NAME=meta["committer_name"],
                      GIT_COMMITTER_EMAIL=meta["committer_email"],
                      GIT_COMMITTER_DATE=meta["committer_date"])
        snapshot = git(repo, "commit-tree", core_tree, "-p", commit, env=frozen,
                       data=meta["message"].encode())
        integrated = apply(features)
        # Plain android14-6.1-lts sublevels get Cogan's GKID-equivalent stack on top.
        stack = gkid_parity.has_stack(git(repo, "show", f"{commit}:{gkid_parity.VERSION_C}"))
        if not stack:
            gkid_parity.apply(repo, cached=True, env=env)
        final = git(repo, "write-tree", env=env)
    return fields["SUBLEVEL"], {"kernel_commit": commit, "core_kernel_tree": core_tree,
                                "kernel_snapshot": snapshot, "integrated_kernel_tree": integrated,
                                "gkid_stack": stack, "final_kernel_tree": final}


def resolve(value, lock):
    verified = sorted(lock["sublevels"], key=int)
    wanted = value.strip().lower()
    if wanted in ("", "lts", "auto"):
        return verified[-1]
    if wanted in verified:
        return wanted
    raise ValueError(f"KSUN+SUSFS is not verified for sublevel {value!r}; "
                     f"use lts or one of: {' '.join(verified)}")


def main(argv):
    try:
        lock = json.loads(FEATURE_LOCK.read_text(encoding="utf-8"))
        if len(argv) == 3 and argv[1] == "resolve":
            print(resolve(argv[2], lock))
            return 0
        if len(argv) == 4 and argv[1] == "record":
            sublevel, entry = identities(Path(argv[2]), argv[3], lock)
            print(json.dumps({sublevel: entry}, indent=2))
            return 0
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + str(exc)[:2000], file=sys.stderr)
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
