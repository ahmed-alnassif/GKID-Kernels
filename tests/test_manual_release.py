#!/usr/bin/env python3
"""Offline tests for Manual Release from Run: which build files it releases, with real job names."""
import hashlib
import io
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/manual-release.yml").read_text())
STEPS = WORKFLOW["jobs"]["manual-release"]["steps"]
STEP = next(step["run"] for step in STEPS if step["name"].startswith("Download the build's files"))
PICK, MERGE, VERIFY = [block.split("\nPY\n", 1)[0] for block in STEP.split("<<'PY'\n")[1:4]]
SOURCES = next(step["run"] for step in STEPS if step["name"] == "Verify source runs")
CHECK_SOURCES = SOURCES.split("<<'PY'\n")[1].split("\nPY\n", 1)[0]
# Job name of run 38864831771 (#17), whose first release failed on the artifact check.
JOB = "build (6.1-KSUN+SUSFS, KSUN, false, true, false, false, 6.1)"
KERNEL = "1-KERNEL_Cogan-6.1.177_KernelSU-Next+SuSFS_v26.10.16-r3.zip"
DIGEST = "sha256:" + "5" * 64


def run(code, directory):
    return subprocess.run([sys.executable, "-I", "-c", code], cwd=directory, capture_output=True, text=True)


def pick(jobs, artifacts):
    """artifacts: (id, name, digest) rows as the API lists them."""
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        (directory / "build-jobs.tsv").write_text("".join(f"{name}\t{result}\n" for name, result in jobs))
        (directory / "run-artifacts.tsv").write_text("".join("\t".join(row) + "\n" for row in artifacts))
        result = run(PICK, directory)
        planned = (directory / "numbered.tsv").read_text().split("\n") if result.returncode == 0 else []
        return result, [line.split("\t")[1] for line in planned if line]


class ManualReleasePickTests(unittest.TestCase):
    def test_releases_the_numbered_downloads_of_the_run(self):
        artifacts = [("1", KERNEL, DIGEST), ("2", "2-MANAGER_KernelSU-Next_v3.4.2.apk", DIGEST),
                     ("3", "3-MANAGER-SPOOFED_KernelSU-Next_v3.4.2.apk", DIGEST),
                     ("4", "4-NOMOUNT-MODULE_v2.1.1.zip", DIGEST),
                     ("5", "build-6.1-KSUN+SUSFS-17", DIGEST), ("6", "build-env-6.1-KSUN+SUSFS-17", DIGEST)]
        result, names = pick([(JOB, "success")], artifacts)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(names, [KERNEL, "2-MANAGER_KernelSU-Next_v3.4.2.apk",
                                 "3-MANAGER-SPOOFED_KernelSU-Next_v3.4.2.apk", "4-NOMOUNT-MODULE_v2.1.1.zip"])

    def test_one_kernel_per_variant(self):
        jobs = [(JOB, "success"), ("build (6.1-BSU+SUSFS, BSU, false, true, false, false, 6.1)", "success")]
        two = [("1", "1-KERNEL_a_6.1-KSUN+SUSFS.zip", DIGEST), ("2", "1-KERNEL_b_6.1-BSU+SUSFS.zip", DIGEST)]
        self.assertEqual(pick(jobs, two)[0].returncode, 0)
        self.assertIn("one 1-KERNEL_ download per variant", pick(jobs, two[:1])[0].stderr)

    def test_failed_job_missing_kernel_or_digest_is_refused(self):
        self.assertIn("Unsuccessful kernel build jobs", pick([(JOB, "failure")], [("1", KERNEL, DIGEST)])[0].stderr)
        self.assertIn("found 0", pick([(JOB, "success")], [("5", "build-6.1-KSUN+SUSFS-17", DIGEST)])[0].stderr)
        self.assertIn("no artifact id or SHA256 digest", pick([(JOB, "success")], [("1", KERNEL, "")])[0].stderr)


def merge(per_run):
    """per_run: [(variants, [(id, name, digest), ...]), ...] as pick.py leaves them per run."""
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        (directory / "all-variants.txt").write_text("".join(v + "\n" for variants, _ in per_run for v in variants))
        (directory / "all-numbered.tsv").write_text("".join("\t".join(row) + "\n" for _, rows in per_run for row in rows))
        result = run(MERGE, directory)
        merged = (directory / "numbered.tsv").read_text().split("\n") if result.returncode == 0 else []
        return result, [line.split("\t")[1] for line in merged if line]


class ManualReleaseSeveralRunsTests(unittest.TestCase):
    KSUN = (["6.1-KSUN+SUSFS"], [("1", KERNEL, DIGEST), ("2", "2-MANAGER_KernelSU-Next_v3.4.2.apk", DIGEST),
                                 ("4", "4-NOMOUNT-MODULE_v2.1.1.zip", "a" * 64)])
    BAKASU = (["6.1-BSU+SUSFS"], [("7", "1-KERNEL_Cogan-6.1.177_BakaSU+SuSFS_v26.10.16-r3.zip", DIGEST),
                                  ("8", "2-MANAGER_BakaSU_v4.2.0-rc3.apk", DIGEST),
                                  ("9", "4-NOMOUNT-MODULE_v2.1.1.zip", "a" * 64)])

    def test_two_variants_make_one_release_with_one_shared_module(self):
        result, names = merge([self.KSUN, self.BAKASU])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(names, [KERNEL, "2-MANAGER_KernelSU-Next_v3.4.2.apk", "4-NOMOUNT-MODULE_v2.1.1.zip",
                                 "1-KERNEL_Cogan-6.1.177_BakaSU+SuSFS_v26.10.16-r3.zip", "2-MANAGER_BakaSU_v4.2.0-rc3.apk"])

    def test_same_variant_twice_or_clashing_files_are_refused(self):
        self.assertIn("same variant is in more than one run", merge([self.KSUN, self.KSUN])[0].stderr)
        clash = (self.BAKASU[0], [*self.BAKASU[1][:2], ("9", "4-NOMOUNT-MODULE_v2.1.1.zip", "b" * 64)])
        self.assertIn("different files with the same name", merge([self.KSUN, clash])[0].stderr)

    def check_sources(self, runs, same_pins=True):
        """runs: [(id, conclusion, created_at)]; each run gets its own commit in a scratch repository."""
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            git = lambda *args: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],  # noqa: E731
                                               cwd=directory, check=True, capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            (directory / "configs").mkdir()
            ids = []
            for index, (run_id, conclusion, created) in enumerate(runs):
                (directory / "configs/upstream.lock").write_text("KSU=1\n" if same_pins or index == 0 else "KSU=2\n")
                (directory / "configs/ksun-susfs-6.1-features.lock.json").write_text("{}")
                (directory / "note").write_text(str(index))
                git("add", "-A")
                git("commit", "-q", "-m", f"c{index}")
                sha = git("rev-parse", "HEAD")
                ids.append(run_id)
                (directory / f"source-run-{run_id}.json").write_text(
                    f'{{"id": {run_id}, "conclusion": "{conclusion}", "event": "workflow_dispatch", "head_branch": "dev",'
                    f' "path": ".github/workflows/build.yml", "head_sha": "{sha}", "created_at": "{created}"}}')
            (directory / "source-runs.txt").write_text("\n".join(ids) + "\n")
            env_file = directory / "env"
            result = subprocess.run([sys.executable, "-I", "-c", CHECK_SOURCES], cwd=directory, capture_output=True,
                                    text=True, env={"GITHUB_ENV": str(env_file), "PATH": "/usr/bin:/bin"})
            table = (directory / "source-runs.tsv").read_text() if result.returncode == 0 else ""
            return result, env_file.read_text() if env_file.exists() else "", table, git("rev-parse", "HEAD")

    def test_runs_from_different_commits_with_the_same_pins(self):
        result, env, table, newest = self.check_sources([("38864831771", "success", "2026-10-16T07:03:44Z"),
                                                         ("38867215760", "success", "2026-10-16T07:26:23Z")])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(env, f"SOURCE_SHA={newest}\n")  # the newest run's commit
        self.assertEqual([line.split("\t")[0] for line in table.splitlines()], ["38864831771", "38867215760"])

    def test_different_pins_or_a_failed_run_are_refused(self):
        result = self.check_sources([("1", "success", "2026-10-16T07:00:00Z"), ("2", "success", "2026-10-16T08:00:00Z")],
                                    same_pins=False)[0]
        self.assertIn("built from different pins", result.stderr)
        result = self.check_sources([("1", "success", "2026-10-16T07:00:00Z"), ("2", "failure", "2026-10-16T08:00:00Z")])[0]
        self.assertIn("Source run 2 did not succeed", result.stderr)
        self.assertIn("tr ', ' '\\n\\n'", SOURCES)  # "1,2", "1, 2" and "1 2" all work


class ManualReleaseVerifyTests(unittest.TestCase):
    def verify(self, content, digest_of):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "release-files").mkdir()
            (directory / "release-files" / KERNEL).write_bytes(content)
            digest = hashlib.sha256(digest_of).hexdigest()
            (directory / "numbered.tsv").write_text(f"1\t{KERNEL}\t{digest}\n")
            result = run(VERIFY, directory)
            return result, (directory / "release-files" / KERNEL).read_bytes()

    def test_raw_and_wrapped_downloads(self):
        kernel = b"PK-kernel-bytes"
        result, data = self.verify(kernel, kernel)
        self.assertEqual(result.returncode, 0, result.stderr)
        wrapped = io.BytesIO()
        with zipfile.ZipFile(wrapped, "w") as archive:
            archive.writestr(KERNEL, kernel)
        result, data = self.verify(wrapped.getvalue(), kernel)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data, kernel)

    def test_wrong_bytes_are_refused(self):
        result, _ = self.verify(b"something else", b"kernel")
        self.assertIn("does not match the build's artifact digest", result.stderr)


class ManualReleaseCreateTests(unittest.TestCase):
    create = next(step["run"] for step in STEPS if step["name"].startswith("Create release"))

    def test_tag_moves_to_the_release_commit_when_workflows_changed(self):
        self.assertIn('workflows_at "$SOURCE_SHA"', self.create)
        self.assertIn('workflows_at "$GITHUB_SHA"', self.create)
        self.assertIn('target="$GITHUB_SHA"', self.create)
        self.assertIn('--target "$target"', self.create)
        self.assertNotIn('--target "$SOURCE_SHA"', self.create)
        self.assertIn("GitHub menolak tag bot di commit lama", self.create)
        self.assertIn('echo "<!-- cogan-source: $SOURCE_SHA -->"', self.create)

    def test_every_download_is_attached_and_listed(self):
        self.assertIn('gh release create "$RELEASE_TAG" release-files/* \\', self.create)
        self.assertIn("--files release-files", self.create)

    def test_whats_new_and_telegram_text(self):
        news = next(step["run"] for step in STEPS if step["name"].startswith("Collect what's new"))
        self.assertIn("cogan-source: ([0-9a-f]{40})", news)
        self.assertIn('git log --format=%B "$prev_source..$SOURCE_SHA" > commit-log.txt', news)
        self.assertIn("git merge-base --is-ancestor", news)
        self.assertIn('--whats-new-file "docs/whats-new/$RELEASE_TAG.md" --commit-log commit-log.txt', self.create)
        self.assertIn("--telegram-out telegram.txt", self.create)
        self.assertIn("--highlights docs/whats-new/highlights.md --previous-notes previous-notes.md", self.create)
        self.assertIn(': > previous-notes.md', news)
        self.assertIn("printf '%s\\n' \"$body\" > previous-notes.md", news)
        self.assertEqual(self.create.count("cat telegram.txt"), 1)  # run summary; the notes carry it in the box
        self.assertIn("--telegram-out telegram.txt --telegram-en-out telegram-en.txt", self.create)
        self.assertEqual(self.create.count("cat telegram-en.txt"), 1)

    def test_run_form_is_indonesian_then_english(self):
        inputs = WORKFLOW[True]["workflow_dispatch"]["inputs"]
        for name in ("run_id", "release_type", "ganti_rilis"):
            indonesian, english = inputs[name]["description"].rsplit(" / ", 1)
            self.assertTrue(indonesian and english, name)
        self.assertTrue(inputs["run_id"]["description"].startswith("ID run build Cogan"))
        checkout = next(step for step in STEPS if step["name"] == "Checkout release scripts")
        self.assertEqual(checkout["with"]["fetch-depth"], 0)

    def test_existing_release_is_replaced_only_when_asked(self):
        self.assertEqual(WORKFLOW[True]["workflow_dispatch"]["inputs"]["ganti_rilis"]["default"], False)
        self.assertIn('if [ "$REPLACE" != "true" ]; then', self.create)
        self.assertIn('gh release delete "$RELEASE_TAG" --repo "$REPO" --yes', self.create)
        # Run 38993943762: replacing a draft (no tag yet) failed on --cleanup-tag.
        self.assertNotIn("--cleanup-tag", self.create)
        self.assertIn('if gh api "repos/$REPO/git/ref/tags/$RELEASE_TAG" > /dev/null 2>&1; then', self.create)
        self.assertIn('gh api -X DELETE "repos/$REPO/git/refs/tags/$RELEASE_TAG"', self.create)


if __name__ == "__main__":
    unittest.main()
