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
    lsm = values.get("CONFIG_LSM", "").strip('"').split(",")
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
        errors = audit(raw, lock)
        print("resolved_config_sha256=" + hashlib.sha256(raw).hexdigest())
        if errors:
            for error in errors:
                print("BLOCKED: " + error, file=sys.stderr)
            return 1
        print("PASS: locked required/forbidden flags and BBG LSM token")
        print("NOTE: this does not prove compiler, link, runtime or production readiness")
        return 0
    except (OSError, ValueError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
