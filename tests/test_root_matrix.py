#!/usr/bin/env python3
"""Offline regression checks for dropdown and legacy BUILD_* matrix."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import yaml

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
        ("KernelSU Next + SUSFS", "KSUN", "true"),
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
    assert 'KSUN_REF="v3.4.2"' in build_script
    assert 'KSUN_EXPECTED_SHA="4c706b5938665866ebe16944a481a7b91e3396af"' in build_script
    assert 'install_ksu "KernelSU-Next/KernelSU-Next" "$KSUN_REF"' in build_script
    # A blocked choice must exit before any tool, download or workspace mutation.
    with tempfile.TemporaryDirectory() as directory:
        env = os.environ.copy()
        env.update(KSU="KSUN", KSU_SUSFS="true", PATH=directory)
        rejected = subprocess.run(
            ["/bin/bash", str(ROOT / "build.sh")], cwd=directory,
            env=env, text=True, capture_output=True,
        )
        assert rejected.returncode == 1, rejected.stderr
        assert 'KSUN+SUSFS is not enabled until compatibility is validated' in rejected.stderr
        assert 'command not found' not in rejected.stderr, rejected.stderr
        assert not list(Path(directory).iterdir()), 'Blocked build changed the workspace'
        # The workflow must reject it in prepare, before cache/dependency jobs.
        workflow = yaml.safe_load((ROOT / ".github/workflows/build.yml").read_text())
        preflight = next(
            step["run"] for step in workflow["jobs"]["prepare"]["steps"]
            if step["name"] == "Validate sublevel, build time and optional features"
        )
        env.update(ROOT_MANAGER_INPUT="KernelSU Next + SUSFS")
        rejected = subprocess.run(
            ["/bin/bash", "-c", preflight], cwd=directory,
            env=env, text=True, capture_output=True,
        )
        assert rejected.returncode == 1, rejected.stderr
        assert 'KSUN+SUSFS is not enabled until compatibility is validated' in rejected.stderr
        assert 'command not found' not in rejected.stderr, rejected.stderr
        assert not list(Path(directory).iterdir()), 'Blocked workflow changed the workspace'
    assert len(entries(matrix(manager="All variants (advanced)"))) == 10
    assert len(entries(matrix(version="All", manager="All variants (advanced)"))) == 50
    assert matrix(manager="invalid", BUILD_KSU=True).returncode != 0
    assert matrix().returncode != 0
    assert matrix(version="0.0", BUILD_KSUN=True).returncode != 0
    print("PASS: root manager dropdown and legacy BUILD_* matrix checks")

if __name__ == "__main__":
    main()
