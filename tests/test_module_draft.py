#!/usr/bin/env python3
"""Offline tests for "Draft modul" (scripts/module_draft.py) with a fake gh."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = sorted(p.parent.name for p in (ROOT / "modules").glob("*/module.prop"))
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
log = os.environ["FAKE_GH_LOG"]
with open(log, "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:3] == ["api", "--paginate"]:
    sys.stdout.write(open(os.environ["FAKE_GH_RELEASES"]).read())
"""


def version(folder):
    prop = dict(l.split("=", 1) for l in (ROOT / "modules" / folder / "module.prop").read_text().splitlines() if "=" in l)
    return prop["version"]


class ModuleDraftTests(unittest.TestCase):
    def run_draft(self, existing, only="semua"):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "bin").mkdir()
            (tmp / "bin/gh").write_text(FAKE_GH)
            (tmp / "bin/gh").chmod(0o755)
            (tmp / "releases.jsonl").write_text("".join(json.dumps(r) + "\n" for r in existing))
            env = dict(os.environ, PATH=f"{tmp / 'bin'}:{os.environ['PATH']}", FAKE_GH_LOG=str(tmp / "log"),
                       FAKE_GH_RELEASES=str(tmp / "releases.jsonl"))
            result = subprocess.run([sys.executable, str(ROOT / "scripts/module_draft.py"), "--repo", "cogan17/Cogan",
                                     "--sha", "a" * 40, "--only", only, "--out", str(tmp / "dist"),
                                     "--summary", str(tmp / "summary.md")], env=env, capture_output=True, text=True)
            if result.returncode:
                raise AssertionError(result.stderr)
            calls = [json.loads(l) for l in (tmp / "log").read_text().splitlines()]
            notes = {p.name: p.read_text() for p in (tmp / "dist").glob("*-notes.md")}
            digests = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (tmp / "dist").glob("*.zip")}
            return calls, notes, digests, (tmp / "summary.md").read_text()

    def creates(self, calls):
        return [c for c in calls if c[:2] == ["release", "create"]]

    def test_first_drafts(self):
        calls, notes, digests, summary = self.run_draft([])
        creates = self.creates(calls)
        self.assertEqual([c[2] for c in creates], [f"{f}-{version(f)}" for f in FOLDERS])
        for call in creates:
            self.assertFalse(call[2].startswith("v"))                     # never looks like a kernel tag
            for flag in ("--draft", "--latest=false"):
                self.assertIn(flag, call)
            self.assertEqual(call[call.index("--target") + 1], "a" * 40)
            self.assertTrue(call[3].endswith(".zip"))
        monitor = notes["thermal-monitor-notes.md"]
        self.assertIn("### Cogan Thermal Monitor", monitor)
        self.assertIn("Draft modul, belum dirilis", monitor)
        self.assertIn("🇬🇧 English", monitor)
        self.assertIn("mencatat **semua suhu**", monitor)                 # the README's first paragraph
        self.assertIn("records **every temperature**", monitor)
        zip_name = f"Cogan-Thermal-Monitor-{version('thermal-monitor')}.zip"
        self.assertIn(f"<!-- cogan-module: thermal-monitor {digests[zip_name]} -->", monitor)
        self.assertIn("draft dibuat", summary)

    def test_up_to_date_draft_is_left_alone(self):
        _, notes, digests, _ = self.run_draft([], only="power-mode")
        zip_name = f"Cogan-Power-Mode-{version('power-mode')}.zip"
        existing = [{"id": 7, "tag_name": f"power-mode-{version('power-mode')}", "draft": True,
                     "body": f"<!-- cogan-module: power-mode {digests[zip_name]} -->"}]
        calls, _, _, summary = self.run_draft(existing, only="power-mode")
        self.assertEqual([c[:2] for c in calls], [["api", "--paginate"]])
        self.assertIn("draft sudah terbaru", summary)

    def test_changed_module_replaces_its_old_drafts(self):
        existing = [
            {"id": 1, "tag_name": "thermal-monitor-v1.0", "draft": True, "body": "<!-- cogan-module: thermal-monitor 00 -->"},
            {"id": 2, "tag_name": f"thermal-monitor-{version('thermal-monitor')}", "draft": True, "body": "old"},
            {"id": 3, "tag_name": "v26.10.16-r3", "draft": True, "body": "kernel draft"},
            {"id": 4, "tag_name": "power-mode-v0.9", "draft": False, "body": "published"},
        ]
        calls, _, _, summary = self.run_draft(existing, only="thermal-monitor")
        deletes = [c[3] for c in calls if c[:3] == ["api", "-X", "DELETE"]]
        self.assertEqual(deletes, ["repos/cogan17/Cogan/releases/1", "repos/cogan17/Cogan/releases/2"])
        self.assertEqual(len(self.creates(calls)), 1)
        self.assertIn("draft diperbarui", summary)

    def test_published_version_is_never_touched(self):
        existing = [{"id": 5, "tag_name": f"power-mode-{version('power-mode')}", "draft": False, "body": ""}]
        calls, _, _, summary = self.run_draft(existing, only="power-mode")
        self.assertEqual(self.creates(calls), [])
        self.assertIn("sudah dirilis", summary)

    def test_workflow(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/module-draft.yml").read_text())
        on = workflow[True]                                                # PyYAML reads "on" as True
        self.assertEqual(on["push"]["branches"], ["dev"])
        self.assertIn("modules/**", on["push"]["paths"])
        options = on["workflow_dispatch"]["inputs"]["modul"]["options"]
        self.assertEqual((options[0], sorted(options[1:])), ("semua", FOLDERS))   # every module can be picked
        self.assertEqual(workflow["permissions"], {"contents": "write"})


if __name__ == "__main__":
    unittest.main()
