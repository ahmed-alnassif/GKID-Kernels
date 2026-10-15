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
        ("KernelSU Next + SUSFS (uji)", "KSUN", "true"),
        ("KernelSU + SUSFS", "KSU", "true"),
        ("BakaSU + SUSFS", "BSU", "true"),
        ("Vanilla", "no", "false"),
    ):
        chosen = entries(matrix(manager=manager, BUILD_VANILLA=True, BUILD_KSU_SUSFS=True))
        assert len(chosen) == 1
        assert chosen[0]["KSU"] == expected_ksu
        assert chosen[0]["KSU_SUSFS"] == expected_susfs
    # KSUN+SUSFS builds only the validated isolated candidate as a test build
    # (Issue #19); any other combination is rejected before tools run.
    build_script = (ROOT / "build.sh").read_text()
    assert 'elif [ "$KSU" = "KSUN" ]; then' in build_script
    assert 'if susfs_included; then' in build_script
    assert 'KSUN+SUSFS test build supports only kernel 6.1.177 (lts)' in build_script
    assert 'scripts/stage_ksun_susfs_candidate.py' in build_script
    assert 'scripts/check_ksun_susfs_resolved_config.py' in build_script
    assert 'KSUN_REF="$PIN_KSUN_REF"' in build_script
    assert 'KSUN_EXPECTED_SHA="$PIN_KSUN_COMMIT"' in build_script
    assert 'install_ksu "KernelSU-Next/KernelSU-Next" "$KSUN_REF"' in build_script
    lock = (ROOT / "configs/upstream.lock").read_text()
    assert "\nKSUN_REF=v3.4.2\n" in lock
    assert "\nKSUN_COMMIT=4c706b5938665866ebe16944a481a7b91e3396af\n" in lock
    workflow = yaml.safe_load((ROOT / ".github/workflows/build.yml").read_text())
    preflight = next(
        step["run"] for step in workflow["jobs"]["prepare"]["steps"]
        if step["name"] == "Validate sublevel, build time and optional features"
    )
    for bad in ({"KERNEL_VERSION": "6.6"}, {"LTO": "thinLTO"}, {"BBG": "false"},
                {"KERNEL_SUBLEVEL": "176"}, {"KSU_COMPAT": "true"}):
        # A rejected choice must exit before any tool, download or workspace mutation.
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.update(KSU="KSUN", KSU_SUSFS="true", PATH=directory, **bad)
            rejected = subprocess.run(
                ["/bin/bash", str(ROOT / "build.sh")], cwd=directory,
                env=env, text=True, capture_output=True,
            )
            assert rejected.returncode == 1, (bad, rejected.stderr)
            assert 'KSUN+SUSFS test build supports only' in rejected.stderr, rejected.stderr
            assert 'command not found' not in rejected.stderr, rejected.stderr
            assert not list(Path(directory).iterdir()), 'Rejected build changed the workspace'
    # The workflow checks the same rules in prepare, before cache/dependency jobs.
    def prepare(**inputs):
        env = {**os.environ, "ROOT_MANAGER_INPUT": "KernelSU Next + SUSFS (uji)",
               "KERNEL_VERSION_INPUT": "6.1", "KERNEL_SUBLEVEL_INPUT": "lts", "BUILD_TIME_INPUT": "N",
               "LTO_INPUT": "fullLTO + NoMount + Clean LTO", "BBG_INPUT": "true", **inputs}
        return subprocess.run(["/bin/bash", "-c", preflight], cwd=ROOT, env=env,
                              text=True, capture_output=True)
    assert prepare().returncode == 0, prepare().stderr
    assert prepare(KERNEL_SUBLEVEL_INPUT="177").returncode == 0
    for bad in ({"KERNEL_VERSION_INPUT": "6.6"}, {"LTO_INPUT": "thinLTO + NoMount + Clean LTO"},
                {"BBG_INPUT": "false"}, {"KERNEL_SUBLEVEL_INPUT": "176"}):
        rejected = prepare(**bad)
        assert rejected.returncode == 1, (bad, rejected.stderr)
        assert 'KSUN+SUSFS (uji)' in rejected.stderr, rejected.stderr
    # Owner-ordered dropdown; the kernel version is locked to 6.1 in the form and in prepare.
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert inputs["ROOT_MANAGER"]["options"] == [
        "KernelSU", "KernelSU + SUSFS", "KernelSU Next", "KernelSU Next + SUSFS (uji)",
        "BakaSU + SUSFS", "Vanilla", "All variants (advanced)"]
    assert inputs["KERNEL_VERSION"]["options"] == ["6.1"]
    assert inputs["KERNEL_VERSION"]["default"] == "6.1"
    for manager in inputs["ROOT_MANAGER"]["options"][:-1]:
        assert len(entries(matrix(manager=manager))) == 1, manager
    other = prepare(ROOT_MANAGER_INPUT="KernelSU", KERNEL_VERSION_INPUT="6.6")
    assert other.returncode == 1 and "kernel 6.1 only" in other.stderr, other.stderr
    assert prepare(ROOT_MANAGER_INPUT="KernelSU").returncode == 0
    assert len(entries(matrix(manager="All variants (advanced)"))) == 10
    assert len(entries(matrix(version="All", manager="All variants (advanced)"))) == 50
    assert matrix(manager="invalid", BUILD_KSU=True).returncode != 0
    assert matrix().returncode != 0
    assert matrix(version="0.0", BUILD_KSUN=True).returncode != 0
    print("PASS: root manager dropdown and legacy BUILD_* matrix checks")

if __name__ == "__main__":
    main()
