#!/usr/bin/env python3
"""Offline tests for the artifact check of Manual Release from Run, with real job names."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/manual-release.yml").read_text())
STEP = next(step["run"] for step in WORKFLOW["jobs"]["manual-release"]["steps"]
            if step["name"] == "Download kernel build artifacts only")
CHECK = STEP.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
# Job name of run 38864831771 (#17), whose release failed on this check.
JOB = "build (6.1-KSUN+SUSFS, KSUN, false, true, false, false, 6.1)"


def check(jobs, artifacts, run_number=17):
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        (directory / "build-jobs.tsv").write_text("".join(f"{name}\t{result}\n" for name, result in jobs))
        (directory / "artifact-names.txt").write_text("".join(name + "\n" for name in artifacts))
        (directory / "source-run.json").write_text(json.dumps({"run_number": run_number}))
        return subprocess.run([sys.executable, "-I", "-c", CHECK], cwd=directory, capture_output=True, text=True)


class ManualReleaseArtifactCheckTests(unittest.TestCase):
    def test_full_matrix_job_name_matches_its_artifact(self):
        result = check([(JOB, "success")], ["build-6.1-KSUN+SUSFS-17"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Verified 1 successful matrix build(s)", result.stdout)

    def test_several_variants(self):
        jobs = [(JOB, "success"), ("build (6.1-BSU+SUSFS, BSU, false, true, false, false, 6.1)", "success")]
        result = check(jobs, ["build-6.1-KSUN+SUSFS-18", "build-6.1-BSU+SUSFS-18"], run_number=18)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_job_or_wrong_artifact_is_refused(self):
        self.assertIn("Unsuccessful kernel build jobs", check([(JOB, "failure")], ["build-6.1-KSUN+SUSFS-17"]).stderr)
        self.assertIn("Artifact mismatch", check([(JOB, "success")], ["build-6.1-KSU-17"]).stderr)
        self.assertIn("Artifact mismatch", check([(JOB, "success")], ["build-6.1-KSUN+SUSFS-16"]).stderr)


if __name__ == "__main__":
    unittest.main()
