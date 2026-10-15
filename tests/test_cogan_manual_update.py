#!/usr/bin/env python3
"""Offline tests for Cogan Manual Update: lock parsing, selection and pin bumps."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import cogan_manual_update as mu

ROOT = Path(__file__).resolve().parents[1]
REAL_LOCK = (ROOT / "configs/upstream.lock").read_text()
NEW = "c" * 40


def fake_lister(overrides=None, tags=None, neutron=None):
    """Upstream equal to the lock, except for explicit overrides."""
    lock = mu.read_lock(REAL_LOCK)
    by_ref = {}
    for key, (_, _, url, ref) in mu.PINS.items():
        if ref != "latest-stable-tag":
            by_ref[(url, ref)] = (overrides or {}).get(key, lock[key])

    def lister(url, *patterns, options=()):
        if url == mu.NEUTRON_REPO:
            return neutron if neutron is not None else {
                "refs/tags/30072026": "a" * 40, "refs/tags/" + lock["NEUTRON_RELEASE"]: "b" * 40}
        if "--tags" in options:
            return tags if tags is not None else {
                "refs/tags/v3.4.0-legacy": "d" * 40,
                "refs/tags/" + lock["KSUN_REF"]: lock["KSUN_COMMIT"],
                "refs/tags/v3.4.1": "e" * 40,
            }
        ref = patterns[0]
        if (url, ref) not in by_ref:
            raise subprocess.CalledProcessError(2, "git")
        return {ref: by_ref[(url, ref)]}
    return lister


class LockTests(unittest.TestCase):
    def test_real_lock_parses_and_has_every_pin(self):
        lock = mu.read_lock(REAL_LOCK)
        sublevels = {key for key in lock if mu.SUBLEVEL_KEY.fullmatch(key)}
        self.assertEqual(set(mu.REQUIRED), set(lock) - sublevels)
        self.assertEqual(sorted(int(key.rsplit("_", 1)[1]) for key in sublevels), list(range(160, 178)))

    def test_unknown_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown lock keys: KSU_COMMMIT"):
            mu.read_lock(REAL_LOCK + "KSU_COMMMIT=" + "a" * 40 + "\n")

    def test_malformed_duplicate_and_missing_lines_rejected(self):
        with self.assertRaisesRegex(ValueError, "Malformed"):
            mu.read_lock(REAL_LOCK.replace("BSU_COMMIT=", "BSU_COMMIT=main\n#", 1))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            mu.read_lock(REAL_LOCK + "KSU_COMMIT=" + "a" * 40 + "\n")
        with self.assertRaisesRegex(ValueError, "missing ANYKERNEL_COMMIT"):
            mu.read_lock("\n".join(l for l in REAL_LOCK.splitlines()
                                   if not l.startswith("ANYKERNEL_COMMIT")))

    def test_write_lock_preserves_comments_and_only_changes_given_keys(self):
        updated = mu.write_lock(REAL_LOCK, {"KSU_COMMIT": NEW})
        before, after = REAL_LOCK.splitlines(), updated.splitlines()
        self.assertEqual(len(before), len(after))
        changed = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(changed, [(next(l for l in before if l.startswith("KSU_COMMIT=")),
                                    "KSU_COMMIT=" + NEW)])

    def test_write_lock_rejects_unknown_key_and_bad_value(self):
        with self.assertRaises(ValueError):
            mu.write_lock(REAL_LOCK, {"NOT_A_PIN": NEW})
        with self.assertRaises(ValueError):
            mu.write_lock(REAL_LOCK, {"KSU_COMMIT": "main"})


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.lock = mu.read_lock(REAL_LOCK)

    def test_everything_up_to_date_proposes_nothing(self):
        rows, updates = mu.plan(self.lock, set(mu.GROUPS), fake_lister())
        self.assertEqual(updates, {})
        self.assertTrue(all(row[-1] == "UP TO DATE" for row in rows))

    def test_update_limited_to_selected_group(self):
        lister = fake_lister({"KSU_COMMIT": NEW, "SUSFS_COMMIT_6_1": NEW})
        _, updates = mu.plan(self.lock, mu.select("susfs"), lister)
        self.assertEqual(updates, {"SUSFS_COMMIT_6_1": NEW})
        rows, updates = mu.plan(self.lock, mu.select("root-managers"), lister)
        self.assertEqual(updates, {"KSU_COMMIT": NEW})
        susfs_row = next(row for row in rows if row[0] == "SUSFS 6.1")
        self.assertEqual(susfs_row[-1], "UPDATE AVAILABLE")  # reported, not changed

    def test_ksun_moves_to_highest_stable_tag_only(self):
        tags = {"refs/tags/v3.4.2": self.lock["KSUN_COMMIT"],
                "refs/tags/v3.5.0-rc1": "f" * 40,
                "refs/tags/v3.10.0-legacy": "d" * 40,
                "refs/tags/v3.4.10": "1" * 40,
                "refs/tags/v3.4.10^{}": NEW}
        _, updates = mu.plan(self.lock, {"root-managers"}, fake_lister(tags=tags))
        self.assertEqual(updates, {"KSUN_REF": "v3.4.10", "KSUN_COMMIT": NEW})

    def test_unreachable_upstream_never_becomes_an_update(self):
        def broken(*_args, **_kwargs):
            raise subprocess.TimeoutExpired("git", 40)
        rows, updates = mu.plan(self.lock, set(mu.GROUPS), broken)
        self.assertEqual(updates, {})
        self.assertTrue(all(row[-1].startswith("UNAVAILABLE") for row in rows))

    def test_kernel_advance_moves_auto_and_adds_the_new_sublevel(self):
        lister = fake_lister({"KERNEL_COMMIT_6_1": NEW})
        rows, updates = mu.plan(self.lock, {"kernel-6.1"}, lister, sublevel_of=lambda commit: 178)
        self.assertEqual(updates, {"KERNEL_COMMIT_6_1": NEW, "KERNEL_COMMIT_6_1_178": NEW})
        row = next(row for row in rows if row[0] == "Kernel GKID 6.1")
        self.assertTrue(row[3].startswith("6.1.177 ") and row[4].startswith("6.1.178 "), row)
        updated = mu.read_lock(mu.write_lock(REAL_LOCK, updates))
        self.assertEqual(updated["KERNEL_COMMIT_6_1_177"], self.lock["KERNEL_COMMIT_6_1"])
        self.assertEqual(updated["KERNEL_COMMIT_6_1_178"], NEW)
        self.assertEqual(mu.current_sublevel(updated), 178)

    def test_new_commit_on_same_sublevel_replaces_that_entry(self):
        lister = fake_lister({"KERNEL_COMMIT_6_1": NEW})
        _, updates = mu.plan(self.lock, {"kernel-6.1"}, lister, sublevel_of=lambda commit: 177)
        self.assertEqual(updates, {"KERNEL_COMMIT_6_1": NEW, "KERNEL_COMMIT_6_1_177": NEW})

    def test_unreadable_sublevel_blocks_the_kernel_update(self):
        def unreadable(commit):
            raise OSError("offline")
        rows, updates = mu.plan(self.lock, {"kernel-6.1"}, fake_lister({"KERNEL_COMMIT_6_1": NEW}),
                                sublevel_of=unreadable)
        self.assertEqual(updates, {})
        row = next(row for row in rows if row[0] == "Kernel GKID 6.1")
        self.assertTrue(row[-1].startswith("UNAVAILABLE: Sublevel unreadable"), row)

    def test_sublevel_parsed_from_makefile_head(self):
        makefile = "# SPDX\nVERSION = 6\nPATCHLEVEL = 1\nSUBLEVEL = 178\nEXTRAVERSION =\n"
        self.assertEqual(mu.kernel_sublevel(NEW, fetch=lambda url: makefile), 178)
        with self.assertRaises(ValueError):
            mu.kernel_sublevel(NEW, fetch=lambda url: makefile.replace("PATCHLEVEL = 1", "PATCHLEVEL = 6"))

    def test_toolchain_moves_to_newest_dated_release_with_its_sha256(self):
        tags = {"refs/tags/06092026": "a" * 40, "refs/tags/01102026": "b" * 40,
                "refs/tags/31122025": "c" * 40, "refs/tags/latest": "d" * 40}
        digest = "e" * 64
        rows, updates = mu.plan(self.lock, {"toolchain"}, fake_lister(neutron=tags),
                                sha256_of=lambda tag: digest)
        self.assertEqual(updates, {"NEUTRON_RELEASE": "01102026", "NEUTRON_SHA256": digest})
        self.assertEqual(mu.read_lock(mu.write_lock(REAL_LOCK, updates))["NEUTRON_RELEASE"], "01102026")
        _, updates = mu.plan(self.lock, {"susfs"}, fake_lister(neutron=tags), sha256_of=lambda tag: digest)
        self.assertEqual(updates, {})  # reported only when toolchain is not selected

    def test_unreadable_toolchain_archive_blocks_the_update(self):
        def broken(tag):
            raise OSError("offline")
        rows, updates = mu.plan(self.lock, {"toolchain"},
                                fake_lister(neutron={"refs/tags/01102026": "b" * 40}), sha256_of=broken)
        self.assertEqual(updates, {})
        self.assertTrue(rows[-1][-1].startswith("UNAVAILABLE: Archive unreadable"), rows[-1])

    def test_unknown_component_rejected(self):
        with self.assertRaises(ValueError):
            mu.select("susfs,kernel-9.9")


class ShellLockTests(unittest.TestCase):
    """functions.sh must accept the real lock and fail closed on bad input."""

    def load(self, text):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "upstream.lock"
            lock.write_text(text)
            script = (f'set -eo pipefail; WORKDIR="{ROOT}"; source "{ROOT}/functions.sh" >/dev/null; '
                      f'load_upstream_lock "{lock}" && echo "$PIN_KSUN_REF $PIN_SUSFS_COMMIT_6_1"')
            return subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                                  env={**os.environ, "GITHUB_ENV": "/dev/null"})

    def test_real_lock_loads(self):
        result = self.load(REAL_LOCK)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lock = mu.read_lock(REAL_LOCK)
        self.assertEqual(result.stdout.split()[-2:], [lock["KSUN_REF"], lock["SUSFS_COMMIT_6_1"]])

    def test_branch_name_instead_of_commit_rejected(self):
        result = self.load(REAL_LOCK.replace("BSU_COMMIT=", "BSU_COMMIT=main\n#", 1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Malformed upstream lock line", result.stdout + result.stderr)

    def test_build_script_reads_every_pin_from_the_lock(self):
        build = (ROOT / "build.sh").read_text()
        self.assertIn('load_upstream_lock "$WORKDIR/configs/upstream.lock" || exit 1', build)
        for name in ("PIN_KSU_COMMIT", "PIN_BSU_COMMIT", "PIN_KSUN_REF", "PIN_KSUN_COMMIT",
                     "PIN_NOMOUNT_SETUP_COMMIT", "PIN_NOMOUNT_COMMIT", "PIN_ANYKERNEL_COMMIT", "PIN_BBG_COMMIT",
                     "PIN_KERNEL_COMMIT_6_1"):
            self.assertIn("$" + name, build, name)
        self.assertNotIn("refs/heads/dev/kernel/setup.sh", build)
        self.assertNotIn("Baseband-guard/raw/main/setup.sh", build)
        self.assertIn('install_pinned_neutron "$WORKDIR/neutron-clang" || exit 1', build)
        self.assertNotIn("antman/main/antman", build)
        functions = (ROOT / "functions.sh").read_text()
        self.assertIn("${PIN_NEUTRON_RELEASE}", functions)
        self.assertIn("${PIN_NEUTRON_SHA256}", functions)
        self.assertIn('if [ "${BBG:-true}" = "true" ]; then', build)
        self.assertIn("features/003-bbg-allow-cache-spinlock.patch", build)
        self.assertNotIn('install_ksu "tiann/KernelSU" "main"', build)
        self.assertNotIn('install_ksu "Baka-SU/BakaSU" "main"', build)
        self.assertIn('SUBLEVEL_PIN_VAR="PIN_KERNEL_COMMIT_6_1_${KERNEL_SUBLEVEL}"', build)
        self.assertNotIn('161) KERNEL_BRANCH=', build)

    def test_sublevel_is_free_text_checked_against_the_lock(self):
        import yaml
        workflow = yaml.safe_load((ROOT / ".github/workflows/build.yml").read_text())
        sublevel = workflow[True]["workflow_dispatch"]["inputs"]["KERNEL_SUBLEVEL"]
        self.assertEqual((sublevel["type"], sublevel["default"]), ("string", "lts"))
        self.assertIn("lts = terbaru", sublevel["description"])
        self.assertIn("6.1.160", sublevel["description"])
        lock = mu.read_lock(REAL_LOCK)
        self.assertEqual(min(int(k.rsplit("_", 1)[1]) for k in lock if mu.SUBLEVEL_KEY.fullmatch(k)), 160)
        self.assertEqual(lock["KERNEL_COMMIT_6_1_" + str(mu.current_sublevel(lock))],
                         lock["KERNEL_COMMIT_6_1"])
        preflight = next(step["run"] for step in workflow["jobs"]["prepare"]["steps"]
                         if step["name"] == "Validate sublevel, build time and optional features")

        def run(version, value):
            env = {**os.environ, "ROOT_MANAGER_INPUT": "KernelSU", "KERNEL_VERSION_INPUT": version,
                   "KERNEL_SUBLEVEL_INPUT": value, "BUILD_TIME_INPUT": "N"}
            return subprocess.run(["bash", "-c", preflight], cwd=ROOT, env=env,
                                  capture_output=True, text=True)
        for value in ("lts", "LTS", "Auto", "", "160", "177"):
            self.assertEqual(run("6.1", value).returncode, 0, value)
        for version, value in (("6.1", "159"), ("6.1", "178"), ("6.1", "6.1.177"),
                               ("6.1", "abc"), ("6.1", "0177"), ("6.6", "177")):
            self.assertNotEqual(run(version, value).returncode, 0, (version, value))
        self.assertIn("Available: lts 160 161", run("6.1", "159").stdout)
        self.assertEqual(run("6.6", "lts").returncode, 0)  # latest needs no 6.1 sublevel

    def test_build_script_maps_lts_to_the_latest_pin(self):
        build = (ROOT / "build.sh").read_text()
        start = build.index('# "lts" (any case), "Auto" or empty')
        end = build.index("\nfi\n", start) + 4
        block = build[start:end]
        lock = mu.read_lock(REAL_LOCK)
        for value, expected in (("lts", lock["KERNEL_COMMIT_6_1"]), ("LTS", lock["KERNEL_COMMIT_6_1"]),
                                ("Auto", lock["KERNEL_COMMIT_6_1"]), ("", lock["KERNEL_COMMIT_6_1"]),
                                ("160", lock["KERNEL_COMMIT_6_1_160"])):
            script = (f'WORKDIR="{ROOT}"; source "{ROOT}/functions.sh" >/dev/null; '
                      f'load_upstream_lock "{ROOT}/configs/upstream.lock"; KERNEL_VERSION=6.1; '
                      f'KERNEL_BRANCH=GKID-6.1; KERNEL_SUBLEVEL="{value}"\n{block}\n'
                      'echo "$KERNEL_SUBLEVEL $KERNEL_BRANCH"')
            result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.split()[-1], expected, value)
            if value != "160":
                self.assertEqual(result.stdout.split()[-2], "Auto", value)

if __name__ == "__main__":
    unittest.main()
