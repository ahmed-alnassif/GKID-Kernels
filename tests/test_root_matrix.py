#!/usr/bin/env python3
"""Offline regression checks for the current legacy BUILD_* matrix."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "py" / "generate-matrix.py"
FLAGS = ("BUILD_VANILLA", "BUILD_KSU", "BUILD_KSUN", "BUILD_KSU_SUSFS")

def matrix(version="6.1", **flags):
    env = os.environ.copy()
    env.update({key: "false" for key in FLAGS})
    env.update({key: str(value).lower() for key, value in flags.items()})
    env["KERNEL_VERSION"] = version
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
    assert matrix().returncode != 0
    assert matrix(version="0.0", BUILD_KSUN=True).returncode != 0
    print("PASS: current BUILD_* matrix regression checks")

if __name__ == "__main__":
    main()
