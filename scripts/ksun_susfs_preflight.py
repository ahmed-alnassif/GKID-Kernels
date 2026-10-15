#!/usr/bin/env python3
"""Read-only preflight for the pinned KSUN+SUSFS candidate.

Usage: python3 scripts/ksun_susfs_preflight.py KERNEL_TREE OUT_DIR KSUN_TREE SUSFS_TREE
Never starts a build or changes the production KSUN+SUSFS gate.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/validation/ksun-susfs-6.1-partial-build.json"

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git_head(path):
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=15,
    )
    return result.stdout.strip()

def main(argv):
    if len(argv) != 5:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    kernel, out, ksun, susfs = map(Path, argv[1:])
    failures = []
    checks = []
    for name, path in (("kernel", kernel), ("ksun", ksun), ("susfs", susfs)):
        expected = evidence["sources"][name]
        try:
            actual = git_head(path)
        except (OSError, subprocess.SubprocessError) as exc:
            actual = "unavailable: " + str(exc)
        ok = actual == expected
        checks.append((name + " HEAD", ok, actual))
        if not ok:
            failures.append(name + " source pin mismatch")
    config = out / ".config"
    if config.is_file():
        actual = sha256(config)
        expected = evidence["configuration"]["sha256"]
        ok = actual == expected
        checks.append((".config SHA256", ok, actual))
        if not ok:
            failures.append(".config differs from tested candidate")
    else:
        checks.append((".config SHA256", False, "missing"))
        failures.append("missing resolved .config")
    for rel, expected in (
        ("fs/susfs.o", evidence["objects"]["core_susfs_sha256"]),
        ("fs/namespace.o", evidence["objects"]["namespace_sha256"]),
    ):
        path = out / rel
        actual = sha256(path) if path.is_file() else "missing"
        ok = actual == expected
        checks.append((rel + " SHA256", ok, actual))
        if not ok:
            failures.append(rel + " missing or changed")
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    if failures:
        print("BLOCKED: no build authorization; " + "; ".join(failures), file=sys.stderr)
        return 1
    print("PREFLIGHT PASS: source/config/objects match recorded evidence.")
    print("NOT a full Image, runtime, toolchain, or device compatibility validation.")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
