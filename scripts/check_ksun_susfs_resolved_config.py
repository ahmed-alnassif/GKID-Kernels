#!/usr/bin/env python3
"""Fail-closed offline audit of a *resolved* KSUN/SUSFS 6.1 .config.

Read-only: does not run Kconfig, compile, download or change kernel files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "configs/ksun-susfs-6.1-features.lock.json"


def audit(config_bytes, lock):
    values = {}
    for raw in config_bytes.decode("utf-8").splitlines():
        if raw.startswith("CONFIG_") and "=" in raw:
            key, value = raw.split("=", 1)
            if key in values:
                raise ValueError("Duplicate config key: " + key)
            values[key] = value
        elif raw.startswith("# CONFIG_") and raw.endswith(" is not set"):
            key = raw[2:-11]
            if key in values:
                raise ValueError("Duplicate config key: " + key)
            values[key] = "n"
    errors = []
    spec = lock["configuration"]
    for key, expected in spec["required"].items():
        if values.get(key, "n") != expected:
            errors.append(f"{key}: expected {expected}, got {values.get(key, 'absent')}")
    for key in spec["forbidden"]:
        if values.get(key, "n") != "n":
            errors.append(f"{key}: forbidden value {values[key]}")
    # Validate every explicitly enabled candidate flag, including ARM64.
    if "fragment" in spec:
        fragment_path = ROOT / spec["fragment"]
        fragment_raw = fragment_path.read_bytes()
        if hashlib.sha256(fragment_raw).hexdigest() != spec["sha256"]:
            raise ValueError("Locked candidate fragment SHA256 mismatch")
        for line in fragment_raw.decode("utf-8").splitlines():
            if line.startswith("CONFIG_LSM="):
                expected_lsm = line.split("=", 1)[1]
                if values.get("CONFIG_LSM") != expected_lsm:
                    errors.append("CONFIG_LSM: resolved list differs from locked fragment")
            if line.startswith("CONFIG_") and line.endswith("=y"):
                key = line.split("=", 1)[0]
                if values.get(key, "n") != "y":
                    errors.append(f"{key}: enabled in locked fragment but not resolved y")
            elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
                key = line[2:-11]
                if values.get(key, "n") != "n":
                    errors.append(f"{key}: disabled in locked fragment but resolved {values[key]}")
    lsm_raw = values.get("CONFIG_LSM", "")
    if not (lsm_raw.startswith('"') and lsm_raw.endswith('"')):
        errors.append("CONFIG_LSM: expected quoted Kconfig string")
    lsm = lsm_raw[1:-1].split(",") if lsm_raw.startswith('"') and lsm_raw.endswith('"') else []
    if "baseband_guard" not in lsm:
        errors.append("CONFIG_LSM: baseband_guard token absent")
    if values.get("CONFIG_KSU_SUSFS", "n") == "y" and values.get("CONFIG_KSU", "n") != "y":
        errors.append("SUSFS enabled without built-in KSU")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Existing final O=/.config after olddefconfig")
    args = parser.parse_args()
    try:
        if args.config.is_symlink():
            raise ValueError("Symlink config is not accepted")
        config = args.config.resolve(strict=True)
        if not config.is_file():
            raise ValueError("Expected regular final config, not symlink")
        raw = config.read_bytes()
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        if lock["configuration"]["target"] != "gki_defconfig":
            raise ValueError("Unexpected locked config target")
        for guard in ("production_enabled", "run_full_build", "release_allowed",
                      "flash_allowed", "lkm_allowed"):
            if lock["guards"].get(guard) is not False:
                raise ValueError("Production guard must remain false: " + guard)
        errors = audit(raw, lock)
        print("resolved_config_sha256=" + hashlib.sha256(raw).hexdigest())
        if errors:
            for error in errors:
                print("BLOCKED: " + error, file=sys.stderr)
            return 1
        print("PASS: locked fragment flags, required/forbidden options, and complete CONFIG_LSM")
        print("NOTE: this does not prove compiler, link, runtime or production readiness")
        return 0
    except (OSError, ValueError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
