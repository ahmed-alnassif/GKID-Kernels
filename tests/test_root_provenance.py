#!/usr/bin/env python3
"""Offline checks for exact refs, annotated tags and moved-tag detection."""
import subprocess
import unittest
from unittest.mock import patch

from scripts import collect_root_provenance as provenance

TAG = "refs/tags/v3.4.2"
COMMIT = "4c706b5938665866ebe16944a481a7b91e3396af"
OTHER = "b" * 40
URL = "https://github.com/KernelSU-Next/KernelSU-Next.git"


class ProvenanceTests(unittest.TestCase):
    def test_build_reference_matches_the_active_baseline(self):
        self.assertEqual(provenance.ksun_build_reference(), (TAG, COMMIT))

    @patch.object(provenance.subprocess, "run")
    def test_lightweight_tag_uses_exact_tag_namespace(self, run):
        run.return_value.stdout = f"{OTHER}\trefs/heads/v3.4.2\n{COMMIT}\t{TAG}\n"
        self.assertEqual(provenance.resolve(URL, TAG), (COMMIT, None))
        self.assertEqual(run.call_args.args[0][-2:], [TAG, TAG + "^{}"])

    @patch.object(provenance.subprocess, "run")
    def test_annotated_tag_returns_the_peeled_commit(self, run):
        run.return_value.stdout = f"{OTHER}\t{TAG}\n{COMMIT}\t{TAG}^{{}}\n"
        self.assertEqual(provenance.resolve(URL, TAG), (COMMIT, None))

    @patch.object(provenance.subprocess, "run")
    def test_branch_does_not_match_a_longer_name(self, run):
        run.return_value.stdout = f"{OTHER}\trefs/heads/main-other\n{COMMIT}\trefs/heads/main\n"
        self.assertEqual(provenance.resolve(URL, "refs/heads/main"), (COMMIT, None))

    @patch.object(provenance.subprocess, "run")
    def test_missing_ref_does_not_fabricate_a_pin(self, run):
        run.return_value.stdout = ""
        sha, error = provenance.resolve(URL, TAG)
        self.assertIsNone(sha)
        self.assertIsNotNone(error)

    @patch.object(provenance.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 20))
    def test_timeout_remains_unresolved(self, run):
        self.assertEqual(provenance.resolve(URL, TAG), (None, "TimeoutExpired"))

    @patch.object(provenance, "resolve", return_value=(OTHER, None))
    def test_moved_tag_is_reported_without_claiming_installed_source(self, resolve):
        ksun = provenance.collect()["root_managers"]["KSUN"]
        self.assertEqual(ksun["git_ref"], TAG)
        self.assertEqual(ksun["resolved_ref_sha"], OTHER)
        self.assertEqual(ksun["expected_build_sha"], COMMIT)
        self.assertIs(ksun["matches_build_pin"], False)
        self.assertIsNotNone(ksun["resolution_error"])
        self.assertIsNone(ksun["installed_source_sha"])

    @patch.object(provenance, "ksun_build_reference", side_effect=ValueError("missing pin"))
    @patch.object(provenance, "resolve", return_value=(OTHER, None))
    def test_missing_build_pin_does_not_fall_back_to_a_branch(self, resolve, build_reference):
        ksun = provenance.collect()["root_managers"]["KSUN"]
        self.assertIsNone(ksun["git_ref"])
        self.assertIsNone(ksun["resolved_ref_sha"])
        self.assertEqual(ksun["resolution_error"], "missing pin")
        self.assertEqual(resolve.call_count, 2)  # Other managers still get inspected.


if __name__ == "__main__":
    unittest.main()
