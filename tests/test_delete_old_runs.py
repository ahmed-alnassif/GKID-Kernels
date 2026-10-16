#!/usr/bin/env python3
"""Offline tests for the run plan of "Hapus log run lama": what is kept, what is deleted."""
import datetime
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/delete-old-runs.yml").read_text())
STEPS = WORKFLOW["jobs"]["delete-old-runs"]["steps"]
PLAN = next(step["run"] for step in STEPS if step["name"] == "Plan which runs to delete")
PLAN_PY = PLAN.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
NOW = datetime.datetime.now(datetime.timezone.utc)


def ago(days):
    return (NOW - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def plan(runs, cited=(), keep_days=7, this_run="99"):
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        (directory / "runs.tsv").write_text("".join("\t".join(run) + "\n" for run in runs))
        (directory / "cited-runs.txt").write_text("".join(c + "\n" for c in cited))
        env = dict(os.environ, KEEP_DAYS=str(keep_days), THIS_RUN=this_run,
                   GITHUB_STEP_SUMMARY=str(directory / "summary.md"))
        result = subprocess.run([sys.executable, "-I", "-c", PLAN_PY], cwd=directory, env=env,
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        return (directory / "delete-plan.txt").read_text().split(), (directory / "summary.md").read_text()


class DeleteOldRunsPlanTests(unittest.TestCase):
    def test_only_old_uncited_completed_runs_are_deleted(self):
        runs = [("11", "completed", ago(30), "Validate"),
                ("12", "completed", ago(1), "Validate"),                  # recent
                ("13", "in_progress", ago(30), "Cogan Kernel Builder"),   # running
                ("38735686355", "completed", ago(30), "Cogan Kernel Builder"),  # cited
                ("99", "completed", ago(30), "Hapus log run lama"),       # this run
                ("14", "completed", ago(8), "Manual Release from Run")]
        deleted, summary = plan(runs, cited=["38735686355"])
        self.assertEqual(deleted, ["11", "14"])
        self.assertIn("Akan dihapus: **2** run", summary)
        self.assertIn("Validate: 1", summary)
        self.assertIn("dirujuk dokumen atau rilis / cited as evidence: 1", summary)

    def test_keep_days_moves_the_cutoff(self):
        runs = [("11", "completed", ago(2), "Validate"), ("12", "completed", ago(5), "Validate")]
        self.assertEqual(plan(runs, keep_days=1)[0], ["11", "12"])
        self.assertEqual(plan(runs, keep_days=3)[0], ["12"])

    def test_workflow_guards(self):
        self.assertIn('-le 90', PLAN)
        self.assertIn("grep -rhoE '\\b[0-9]{11}\\b' docs configs README.md README.en.md", PLAN)
        self.assertIn("actions/runs/[0-9]+", PLAN)
        delete = next(step for step in STEPS if step["name"] == "Delete the planned runs")
        self.assertEqual(delete["if"], "inputs.konfirmasi == 'HAPUS'")
        self.assertIn("limit=800", delete["run"])
        self.assertEqual(WORKFLOW["permissions"], {"actions": "write", "contents": "read"})

    def test_documented_evidence_runs_are_found(self):
        cited = subprocess.run(["bash", "-c", "grep -rhoE '\\b[0-9]{11}\\b' docs configs README.md README.en.md"],
                               cwd=ROOT, capture_output=True, text=True).stdout.split()
        self.assertIn("38735686355", cited)  # pin baseline run (WORK-AGREEMENT)
        # The r3 build is cited only by its release notes ("built from run [ID](…/actions/runs/ID)").
        body = "Dibangun dari / built from run [38864831771](https://github.com/cogan17/Cogan/actions/runs/38864831771)"
        from_release = subprocess.run(["bash", "-c", "grep -oE 'actions/runs/[0-9]+' | cut -d/ -f3"], input=body,
                                      capture_output=True, text=True).stdout.split()
        self.assertEqual(from_release, ["38864831771"])


if __name__ == "__main__":
    unittest.main()
