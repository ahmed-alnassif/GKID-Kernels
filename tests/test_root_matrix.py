#!/usr/bin/env python3
"""Offline regression checks for dropdown and legacy BUILD_* matrix."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "py" / "generate-matrix.py"
FLAGS = ("BUILD_VANILLA", "BUILD_KSU", "BUILD_KSUN", "BUILD_KSU_SUSFS")

def matrix(version="6.1", manager="", **flags):
    env = os.environ.copy()
    env.update({key: "false" for key in FLAGS})
    env.update({key: str(value).lower() for key, value in flags.items()})
    env["KERNEL_VERSION"] = version
    env["ROOT_MANAGER"] = manager
    return subprocess.run([sys.executable, str(SCRIPT)], env=env, text=True, capture_output=True)

def entries(result):
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.split("matrix=", 1)[1])["include"]

def main():
    assert len(entries(matrix(BUILD_VANILLA=True))) == 2
    assert len(entries(matrix(BUILD_KSU=True))) == 1
    ksun = entries(matrix(BUILD_KSUN=True))
    assert len(ksun) == 1 and ksun[0]["KSU"] == "KSUN"
    assert ksun[0]["KSU_SUSFS"] == "false"
    assert len(entries(matrix(BUILD_KSU_SUSFS=True))) == 6
    assert len(entries(matrix(BUILD_VANILLA=True, BUILD_KSU=True, BUILD_KSU_SUSFS=True))) == 9
    assert len(entries(matrix(version="All", BUILD_KSUN=True))) == 5
    assert len(entries(matrix(version="All", BUILD_VANILLA=True, BUILD_KSU=True, BUILD_KSU_SUSFS=True))) == 45
    # Explicit dropdown selections override legacy checkboxes and yield one variant.
    for manager, expected_ksu, expected_susfs in (
        ("KernelSU", "KSU", "false"),
        ("KernelSU Next", "KSUN", "false"),
        ("KernelSU + SUSFS", "KSU", "true"),
        ("BakaSU + SUSFS", "BSU", "true"),
        ("Vanilla", "no", "false"),
    ):
        chosen = entries(matrix(manager=manager, BUILD_VANILLA=True, BUILD_KSU_SUSFS=True))
        assert len(chosen) == 1
        assert chosen[0]["KSU"] == expected_ksu
        assert chosen[0]["KSU_SUSFS"] == expected_susfs
    # Guard the unsupported KSUN+SUSFS combination until upstream compatibility
    # and a targeted build/runtime test have been verified (Issue #19).
    build_script = (ROOT / "build.sh").read_text()
    assert 'if [ "$KSU" = "KSUN" ]; then' in build_script
    assert 'if susfs_included; then' in build_script
    assert 'KSUN+SUSFS is not enabled until compatibility is validated' in build_script
    assert 'install_ksu "KernelSU-Next/KernelSU-Next" "next"' in build_script
    assert len(entries(matrix(manager="All variants (advanced)"))) == 10
    assert len(entries(matrix(version="All", manager="All variants (advanced)"))) == 50
    assert matrix(manager="invalid", BUILD_KSU=True).returncode != 0
    assert matrix().returncode != 0
    assert matrix(version="0.0", BUILD_KSUN=True).returncode != 0
    print("PASS: root manager dropdown and legacy BUILD_* matrix checks")

if __name__ == "__main__":
    main()
