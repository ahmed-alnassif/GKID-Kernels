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
    # Both SUSFS root managers in one run (KSUN + SUSFS and BakaSU + SUSFS).
    both = entries(matrix(manager="KSUN + SUSFS & BakaSU + SUSFS", BUILD_VANILLA=True))
    assert [(e["name"], e["KSU"], e["KSU_SUSFS"]) for e in both] == [
        ("6.1-KSUN+SUSFS", "KSUN", "true"), ("6.1-BSU+SUSFS", "BSU", "true")]
    # KSUN+SUSFS builds only the validated, device-tested isolated candidate (Issue #19)
    # on a sublevel with locked trees; anything else is rejected before tools run.
    build_script = (ROOT / "build.sh").read_text()
    assert 'elif [ "$KSU" = "KSUN" ]; then' in build_script
    assert 'if susfs_included; then' in build_script
    assert 'KSUN+SUSFS supports only kernel 6.1, fullLTO' in build_script
    assert 'stage_ksun_susfs_candidate.py" "$KSRC" "$WORKDIR/ksun" "$KSUN_SUSFS_SUBLEVEL"' in build_script
    assert '+Test' not in build_script  # no longer labelled as a test build
    # One build tag everywhere (revision, else CI run) and cogan17@GKID.
    assert 'SUFFIX="${RUN_NUM}-${LATEST_COMMIT_HASH}"' in build_script
    assert 'RUN_NUM="-$BUILD_REVISION"\n' in build_script
    assert '-$BUILD_REVISION${RUN_NUM' not in build_script
    assert 'USER="cogan17"' in build_script and 'HOST="GKID"' in build_script
    assert 'ahmed-alnassif"' not in build_script.split('ANYKERNEL_REPO')[0]
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
    def early(**variables):
        # A rejected choice must exit before any tool, download or workspace mutation:
        # only python3 (the read-only sublevel check) is on PATH.
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as tools:
            os.symlink(sys.executable, Path(tools) / "python3")
            env = os.environ.copy()
            env.update(PATH=tools, **variables)
            result = subprocess.run(
                ["/bin/bash", str(ROOT / "build.sh")], cwd=directory,
                env=env, text=True, capture_output=True,
            )
            assert not list(Path(directory).iterdir()), "Rejected build changed the workspace"
            return result
    for bad, message in (({"KERNEL_VERSION": "6.6"}, "KSUN+SUSFS supports only"),
                         ({"LTO": "thinLTO"}, "KSUN+SUSFS supports only"),
                         ({"BBG": "false"}, "KSUN+SUSFS supports only"),
                         ({"KSU_COMPAT": "true"}, "KSUN+SUSFS supports only"),
                         ({"KERNEL_SUBLEVEL": "166"}, "KSUN+SUSFS is not verified"),
                         ({"KERNEL_SUBLEVEL": "6.1.177"}, "KSUN+SUSFS is not verified")):
        rejected = early(KSU="KSUN", KSU_SUSFS="true", **bad)
        assert rejected.returncode == 1, (bad, rejected.stderr)
        assert message in rejected.stderr, rejected.stderr
        assert 'command not found' not in rejected.stderr, rejected.stderr
    # Every SUSFS variant needs 6.1.167+ (the SUSFS kernel patch needs its fs/namespace.c context).
    for ksu in ("BSU", "KSU"):
        rejected = early(KSU=ksu, KSU_SUSFS="true", KERNEL_SUBLEVEL="166")
        assert rejected.returncode == 1, (ksu, rejected.stderr)
        assert 'SUSFS variants need kernel 6.1.167 or newer' in rejected.stderr, rejected.stderr
    # Cogan is the generic GKI 6.1 kernel and must not be disturbed by device work (A18):
    # device builds (Xiaomi 14T Pro / rothko) live in their own repository with their own
    # copy of this engine (cogan17/Xiomi-14t-pro, D-021), never in Cogan's code.
    code = [ROOT / "build.sh", ROOT / "functions.sh", *ROOT.glob("scripts/*.py"), *ROOT.glob("py/*.py"),
            *ROOT.glob("configs/*"), *ROOT.glob(".github/workflows/*.yml"), *ROOT.glob(".github/scripts/*.py")]
    for path in code:
        text = path.read_text(encoding="utf-8", errors="replace")
        for device_code in ("TARGET_DEVICE", "KERNEL_SOURCE=", "rothko", "Xiomi", "kmi_compat", "COGAN_MIRROR_REPO"):
            assert device_code not in text, f"{path.relative_to(ROOT)}: {device_code} (device code belongs in its own repository, A18)"
    # The workflow checks the same rules in prepare, before cache/dependency jobs.
    def prepare(**inputs):
        env = {**os.environ, "ROOT_MANAGER_INPUT": "KernelSU Next + SUSFS",
               "KERNEL_VERSION_INPUT": "6.1", "KERNEL_SUBLEVEL_INPUT": "lts", "BUILD_TIME_INPUT": "N",
               "LTO_INPUT": "fullLTO + NoMount + Clean LTO", "BBG_INPUT": "true", **inputs}
        return subprocess.run(["/bin/bash", "-c", preflight], cwd=ROOT, env=env,
                              text=True, capture_output=True)
    assert prepare().returncode == 0, prepare().stderr
    for sublevel in ("177", "176", "168", "167"):
        assert prepare(KERNEL_SUBLEVEL_INPUT=sublevel).returncode == 0, sublevel
    for bad in ({"KERNEL_VERSION_INPUT": "6.6"}, {"LTO_INPUT": "thinLTO + NoMount + Clean LTO"},
                {"BBG_INPUT": "false"}, {"KERNEL_SUBLEVEL_INPUT": "166"},
                {"ROOT_MANAGER_INPUT": "KSUN + SUSFS & BakaSU + SUSFS", "KERNEL_SUBLEVEL_INPUT": "160"}):
        rejected = prepare(**bad)
        assert rejected.returncode == 1, (bad, rejected.stderr)
        assert 'KSUN+SUSFS needs' in rejected.stderr or 'KSUN+SUSFS is not verified' in rejected.stderr, rejected.stderr
    # SUSFS variants: 6.1.167 and newer; variants without SUSFS keep 160+.
    for manager in ("BakaSU + SUSFS", "KernelSU + SUSFS", "All variants (advanced)"):
        rejected = prepare(ROOT_MANAGER_INPUT=manager, KERNEL_SUBLEVEL_INPUT="166")
        assert rejected.returncode == 1 and "SUSFS variants need kernel 6.1.167" in rejected.stdout, (manager, rejected)
        assert prepare(ROOT_MANAGER_INPUT=manager, KERNEL_SUBLEVEL_INPUT="167").returncode == 0, manager
    for manager in ("KernelSU", "KernelSU Next", "Vanilla"):
        assert prepare(ROOT_MANAGER_INPUT=manager, KERNEL_SUBLEVEL_INPUT="160").returncode == 0, manager
    # Owner-ordered dropdown; the kernel version is locked to 6.1 in the form and in prepare.
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert inputs["ROOT_MANAGER"]["options"] == [
        "KernelSU", "KernelSU + SUSFS", "KernelSU Next", "KernelSU Next + SUSFS",
        "BakaSU + SUSFS", "KSUN + SUSFS & BakaSU + SUSFS", "Vanilla", "All variants (advanced)"]
    assert inputs["KERNEL_VERSION"]["options"] == ["6.1"]
    assert inputs["KERNEL_VERSION"]["default"] == "6.1"
    # The Cogan form stays generic (no device option).
    assert "DEVICE" not in inputs
    run_build = next(step for step in workflow["jobs"]["build"]["steps"] if step["name"] == "Run Build Script")
    assert "TARGET_DEVICE" not in run_build["env"]
    for manager in inputs["ROOT_MANAGER"]["options"][:-1]:
        expected = 2 if manager == "KSUN + SUSFS & BakaSU + SUSFS" else 1
        assert len(entries(matrix(manager=manager))) == expected, manager
    other = prepare(ROOT_MANAGER_INPUT="KernelSU", KERNEL_VERSION_INPUT="6.6")
    assert other.returncode == 1 and "kernel 6.1 only" in other.stderr, other.stderr
    assert prepare(ROOT_MANAGER_INPUT="KernelSU").returncode == 0
    # Kernel, manager, spoofed manager and NoMount are uploaded as-is (no ZIP-in-ZIP) under
    # numbered names; the release job only takes build-* artifacts.
    build_steps = workflow["jobs"]["build"]["steps"]
    uploads = {step["name"]: step for step in build_steps if str(step.get("name", "")).startswith("Upload ")
               and step["name"][7:8].isdigit()}
    assert sorted(uploads) == ["Upload 1 - kernel", "Upload 2 - root manager",
                               "Upload 3 - spoofed root manager", "Upload 4 - NoMount module"], sorted(uploads)
    for step in uploads.values():
        assert step["with"]["archive"] is False and "name" not in step["with"], step
        assert step["if"].startswith("always() && steps.downloads.outputs."), step
    assert "upload-all" not in workflow["jobs"]
    downloads = [step for step in workflow["jobs"]["release"]["steps"]
                 if str(step.get("uses", "")).startswith("actions/download-artifact")]
    assert downloads and all(step["with"].get("pattern") == "build-*" for step in downloads)
    assert 'GKI_RELEASES_REPO="https://github.com/${GITHUB_REPOSITORY:-cogan17/Cogan}"' in build_script
    assert len(entries(matrix(manager="All variants (advanced)"))) == 10
    assert len(entries(matrix(version="All", manager="All variants (advanced)"))) == 50
    assert matrix(manager="invalid", BUILD_KSU=True).returncode != 0
    assert matrix().returncode != 0
    assert matrix(version="0.0", BUILD_KSUN=True).returncode != 0
    print("PASS: root manager dropdown and legacy BUILD_* matrix checks")

if __name__ == "__main__":
    main()
