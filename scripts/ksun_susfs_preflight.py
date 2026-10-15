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
LOCK = ROOT / "configs/ksun-susfs-6.1.lock.json"

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git_head(path):
    path = path.resolve(strict=True)
    # A linked Git worktree has a .git *file*, not necessarily a directory.
    if not (path / ".git").exists():
        raise ValueError("source directory is not a Git checkout/worktree root")
    top = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True, timeout=15,
    ).stdout.strip()
    if Path(top).resolve() != path:
        raise ValueError("source path must be the checkout root")
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=15,
    )
    return result.stdout.strip()

def lock_consistency(lock, evidence):
    """Return mismatches between immutable candidate pins and recorded evidence."""
    errors = []
    for name in ("kernel", "ksun", "susfs"):
        if lock["sources"][name]["commit"] != evidence["sources"][name]:
            errors.append(f"{name} lock/evidence commit mismatch")
    if lock["toolchain"]["archive_sha256"] != evidence["toolchain"]["archive_sha256"]:
        errors.append("toolchain lock/evidence SHA256 mismatch")
    if lock["build_enabled"] is not False:
        errors.append("build gate must remain disabled")
    if lock["validation"]["full_image_verified"] is not False or lock["validation"]["runtime_verified"] is not False:
        errors.append("unverified full build/runtime must not be marked verified")
    return errors


def main(argv):
    if len(argv) != 5:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    lock_errors = lock_consistency(lock, evidence)
    kernel, out, ksun, susfs = map(Path, argv[1:])
    failures = list(lock_errors)
    for error in lock_errors:
        print("FAIL candidate lock: " + error)
    checks = []
    for name, path in (("kernel", kernel), ("ksun", ksun), ("susfs", susfs)):
        expected = evidence["sources"][name]
        try:
            actual = git_head(path)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
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
    driver_archive = out / "drivers/kernelsu/built-in.a"
    archive_ok = driver_archive.is_file() and driver_archive.stat().st_size > 0
    checks.append(("KSUN built-in.a exists", archive_ok, str(driver_archive)))
    if not archive_ok:
        failures.append("KSUN built-in archive missing")
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
