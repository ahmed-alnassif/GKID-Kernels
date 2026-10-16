#!/usr/bin/env python3
"""Offline tests for Cogan Manual Update: lock parsing, selection and pin bumps."""
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

from scripts import cogan_manual_update as mu

ROOT = Path(__file__).resolve().parents[1]
REAL_LOCK = (ROOT / "configs/upstream.lock").read_text()
NEW = "c" * 40
# Release tags and companion assets as Cogan Manual Update records them.
COMPANION_FIXTURE = {
    "KSU_REF": "v3.3.1", "BSU_REF": "v4.2.0-rc3", "NOMOUNT_REF": "v2.1.1",
    "KSU_MANAGER_APK": "KernelSU_v3.3.1_32211-release.apk", "KSU_MANAGER_SHA256": "1" * 64,
    "BSU_MANAGER_APK": "BakaSU_v4.2.0-rc3_35222-release.apk", "BSU_MANAGER_SHA256": "2" * 64,
    "KSUN_MANAGER_APK": "KernelSU_Next_v3.4.2_33355-release.apk", "KSUN_MANAGER_SHA256": "3" * 64,
    # KernelSU Next publishes a spoofed manager; this BakaSU release does not.
    "KSUN_SPOOFED_APK": "KernelSU_Next_v3.4.2_33355-spoofed-release.apk", "KSUN_SPOOFED_SHA256": "5" * 64,
    "NOMOUNT_MODULE_ZIP": "NoMount-v2.1.1-release-7046c7a-120.zip", "NOMOUNT_MODULE_SHA256": "4" * 64,
}
# BakaSU without a spoofed pin, whatever the real lock holds.
FULL_LOCK = mu.write_lock(REAL_LOCK, {**COMPANION_FIXTURE, "BSU_SPOOFED_APK": None, "BSU_SPOOFED_SHA256": None})
# The lock before any release-tag update: no optional keys at all.
BARE_LOCK = "".join(line + "\n" for line in REAL_LOCK.splitlines()
                    if line.split("=", 1)[0] not in mu.ANCHORS)


def fake_lister(overrides=None, tags=None, neutron=None, lock_text=None):
    """Upstream equal to the lock, except for explicit overrides."""
    lock = mu.read_lock(lock_text or FULL_LOCK)
    by_ref, by_url_tags = {}, {}
    for key, (_, _, url, ref) in mu.PINS.items():
        commit = (overrides or {}).get(key, lock[key])
        if ref.startswith("latest-"):
            tag = lock.get(mu.TAG_KEYS[key]) or COMPANION_FIXTURE[mu.TAG_KEYS[key]]
            by_url_tags[url] = {"refs/tags/v0.0.1": "d" * 40, "refs/tags/v9.0.0-legacy": "e" * 40,
                                "refs/tags/" + tag: commit}
        else:
            by_ref[(url, ref)] = commit
    if tags is not None:
        by_url_tags[mu.PINS["KSUN_COMMIT"][2]] = tags

    def lister(url, *patterns, options=()):
        if url == mu.NEUTRON_REPO:
            return neutron if neutron is not None else {
                "refs/tags/30072026": "a" * 40, "refs/tags/" + lock["NEUTRON_RELEASE"]: "b" * 40}
        if "--tags" in options:
            if url not in by_url_tags:
                raise subprocess.CalledProcessError(2, "git")
            return by_url_tags[url]
        ref = patterns[0]
        if (url, ref) not in by_ref:
            raise subprocess.CalledProcessError(2, "git")
        return {ref: by_ref[(url, ref)]}
    return lister


def fake_assets(drop=()):
    """Release assets: the recorded companions plus a debug APK and a bare binary.

    drop names pin keys (whole release missing) or asset keys (that asset missing).
    """
    def assets_of(repo, tag):
        assets = []
        for key, companions in mu.COMPANIONS.items():
            for companion in companions:
                if companion.repo != repo or key in drop or companion.name_key in drop \
                        or companion.name_key not in COMPANION_FIXTURE:
                    continue
                name = COMPANION_FIXTURE[companion.name_key]
                assets.append({"name": name, "url": "https://example.invalid/" + name,
                               "digest": "sha256:" + COMPANION_FIXTURE[companion.sha_key]})
        if assets:
            assets += [{"name": "manager-debug.apk", "url": "https://example.invalid/d", "digest": ""},
                       {"name": "ksud-aarch64-linux-android", "url": "https://example.invalid/k", "digest": ""}]
        return assets
    return assets_of


def no_ci_artifact(repo, ci, commit, tag):
    raise ValueError("no unexpired artifact")


def apk_bytes(label=b"apk"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as apk:
        apk.writestr("AndroidManifest.xml", label)
        apk.writestr("classes.dex", label)
    return buffer.getvalue()


def plan(lock, groups, lister, **kwargs):
    kwargs.setdefault("assets_of", fake_assets())
    kwargs.setdefault("ci_of", no_ci_artifact)  # never reach the real Actions API in tests
    return mu.plan(lock, groups, lister, **kwargs)


class LockTests(unittest.TestCase):
    def test_real_lock_parses_and_has_every_pin(self):
        lock = mu.read_lock(REAL_LOCK)
        sublevels = {key for key in lock if mu.SUBLEVEL_KEY.fullmatch(key)}
        self.assertLessEqual(set(mu.REQUIRED), set(lock) - sublevels)
        self.assertLessEqual(set(lock) - sublevels - set(mu.REQUIRED), set(mu.OPTIONAL))
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

    def test_every_key_family_has_one_value_shape(self):
        for key, value in (("KSU_REF", "main"), ("KSU_REF", "a" * 40), ("BSU_MANAGER_APK", "x.zip"),
                           ("NOMOUNT_MODULE_ZIP", "x.apk"), ("KSU_MANAGER_SHA256", "a" * 40),
                           ("KSU_COMMIT", "v3.3.1"), ("SUSFS_COMMIT_6_1", "1" * 64)):
            with self.assertRaisesRegex(ValueError, "Bad value|Malformed", msg=key):
                mu.read_lock(mu.write_lock(FULL_LOCK, {}).replace(
                    next(l for l in FULL_LOCK.splitlines() if l.startswith(key + "=")), f"{key}={value}"))
        self.assertEqual(mu.read_lock(FULL_LOCK)["BSU_REF"], "v4.2.0-rc3")

    def test_write_lock_rejects_unknown_key_and_bad_value(self):
        with self.assertRaises(ValueError):
            mu.write_lock(REAL_LOCK, {"NOT_A_PIN": NEW})
        with self.assertRaises(ValueError):
            mu.write_lock(REAL_LOCK, {"KSU_COMMIT": "main"})


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.lock = mu.read_lock(FULL_LOCK)

    def test_everything_up_to_date_proposes_nothing(self):
        rows, updates = plan(self.lock, set(mu.GROUPS), fake_lister())
        self.assertEqual(updates, {})
        self.assertTrue(all(row[-1].startswith("UP TO DATE") for row in rows), rows)
        bakasu = next(row for row in rows if row[0] == "BakaSU")
        self.assertIn("no usable spoofed .apk", bakasu[-1])  # noted, never blocking

    def test_update_limited_to_selected_group(self):
        lister = fake_lister({"KSU_COMMIT": NEW, "SUSFS_COMMIT_6_1": NEW})
        _, updates = plan(self.lock, mu.select("susfs"), lister)
        self.assertEqual(updates, {"SUSFS_COMMIT_6_1": NEW})
        rows, updates = plan(self.lock, mu.select("root-managers"), lister)
        self.assertEqual(updates, {"KSU_COMMIT": NEW})
        susfs_row = next(row for row in rows if row[0] == "SUSFS 6.1")
        self.assertEqual(susfs_row[-1], "UPDATE AVAILABLE")  # reported, not changed

    def test_ksun_moves_to_highest_stable_tag_only(self):
        tags = {"refs/tags/v3.4.2": self.lock["KSUN_COMMIT"],
                "refs/tags/v3.5.0-rc1": "f" * 40,
                "refs/tags/v3.10.0-legacy": "d" * 40,
                "refs/tags/v3.4.10": "1" * 40,
                "refs/tags/v3.4.10^{}": NEW}
        _, updates = plan(self.lock, {"root-managers"}, fake_lister(tags=tags))
        self.assertEqual(updates, {"KSUN_REF": "v3.4.10", "KSUN_COMMIT": NEW})

    def test_release_tag_pins_record_tag_and_matching_assets(self):
        bare = mu.read_lock(BARE_LOCK)
        commits = {"KSU_COMMIT": "1" * 40, "BSU_COMMIT": "2" * 40, "NOMOUNT_COMMIT": "4" * 40}
        rows, updates = plan(bare, {"root-managers", "nomount"},
                             fake_lister(commits, lock_text=BARE_LOCK))
        for key, value in COMPANION_FIXTURE.items():
            if key != "KSUN_REF":
                self.assertEqual(updates.get(key), value, key)
        self.assertEqual(updates["KSU_COMMIT"], "1" * 40)
        self.assertEqual(updates["BSU_COMMIT"], "2" * 40)
        row = next(row for row in rows if row[0] == "BakaSU")
        self.assertIn("v4.2.0-rc3", row[4])
        self.assertIn(COMPANION_FIXTURE["BSU_MANAGER_APK"], row[4])
        lines = mu.write_lock(BARE_LOCK, updates).splitlines()
        start = lines.index("KSU_COMMIT=" + "1" * 40)
        self.assertEqual(lines[start + 1:start + 4], [
            "KSU_REF=v3.3.1", "KSU_MANAGER_APK=" + COMPANION_FIXTURE["KSU_MANAGER_APK"],
            "KSU_MANAGER_SHA256=" + "1" * 64])
        mu.read_lock("\n".join(lines) + "\n")

    def test_missing_manager_apk_keeps_that_root_manager_pinned(self):
        bare = mu.read_lock(BARE_LOCK)
        rows, updates = plan(bare, {"root-managers"}, fake_lister({"BSU_COMMIT": NEW}, lock_text=BARE_LOCK),
                             assets_of=fake_assets(drop=("BSU_COMMIT",)))
        self.assertFalse({"BSU_COMMIT", "BSU_REF", "BSU_MANAGER_APK"} & set(updates))
        self.assertIn("KSU_REF", updates)
        row = next(row for row in rows if row[0] == "BakaSU")
        self.assertTrue(row[-1].startswith("UNAVAILABLE: no usable .apk"), row)

    def test_nomount_without_module_zip_still_follows_the_tag(self):
        bare = mu.read_lock(BARE_LOCK)
        rows, updates = plan(bare, {"nomount"}, fake_lister({"NOMOUNT_COMMIT": NEW}, lock_text=BARE_LOCK),
                             assets_of=fake_assets(drop=("NOMOUNT_COMMIT",)))
        self.assertEqual(updates["NOMOUNT_COMMIT"], NEW)
        self.assertEqual(updates["NOMOUNT_REF"], "v2.1.1")
        self.assertNotIn("NOMOUNT_MODULE_ZIP", updates)
        row = next(row for row in rows if row[0] == "NoMount source")
        self.assertIn("no usable .zip", row[-1])

    def test_spoofed_manager_is_pinned_only_when_the_release_publishes_it(self):
        bare = mu.read_lock(BARE_LOCK)
        _, updates = plan(bare, {"root-managers"}, fake_lister(lock_text=BARE_LOCK))
        self.assertEqual(updates["KSUN_SPOOFED_APK"], COMPANION_FIXTURE["KSUN_SPOOFED_APK"])
        self.assertEqual(updates["KSUN_SPOOFED_SHA256"], "5" * 64)
        self.assertNotIn("BSU_SPOOFED_APK", updates)
        lines = mu.write_lock(BARE_LOCK, updates).splitlines()
        start = lines.index("KSUN_COMMIT=" + bare["KSUN_COMMIT"])
        self.assertEqual([line.split("=")[0] for line in lines[start + 1:start + 5]],
                         ["KSUN_MANAGER_APK", "KSUN_MANAGER_SHA256", "KSUN_SPOOFED_APK", "KSUN_SPOOFED_SHA256"])

    def test_spoofed_manager_dropped_by_a_new_release_is_removed(self):
        tags = {"refs/tags/v3.4.3": NEW}
        _, updates = plan(self.lock, {"root-managers"}, fake_lister(tags=tags),
                          assets_of=fake_assets(drop=("KSUN_SPOOFED_APK",)))
        self.assertEqual(updates["KSUN_REF"], "v3.4.3")
        self.assertIsNone(updates["KSUN_SPOOFED_APK"])
        self.assertIsNone(updates["KSUN_SPOOFED_SHA256"])
        written = mu.read_lock(mu.write_lock(FULL_LOCK, updates))
        self.assertNotIn("KSUN_SPOOFED_APK", written)
        self.assertEqual(written["KSUN_MANAGER_APK"], COMPANION_FIXTURE["KSUN_MANAGER_APK"])
        with self.assertRaisesRegex(ValueError, "Only optional keys"):
            mu.write_lock(FULL_LOCK, {"KSU_COMMIT": None})

    def test_bakasu_spoofed_comes_from_the_tag_run_artifact_and_waits_for_the_mirror(self):
        mu.PENDING_MIRROR.clear()
        data = apk_bytes(b"spoofed")
        seen = []

        def ci_of(repo, ci, commit, tag):
            seen.append((repo, ci, commit, tag))
            return "ReSukiSU_v4.2.0-rc3_35171-universal-release.apk", data, "https://example.invalid/run"
        _, updates = plan(self.lock, {"root-managers"}, fake_lister(), ci_of=ci_of)
        name = "BakaSU-spoofed_ReSukiSU_v4.2.0-rc3_35171-universal-release.apk"
        self.assertEqual(updates["BSU_SPOOFED_APK"], name)
        self.assertEqual(updates["BSU_SPOOFED_SHA256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(seen, [("Baka-SU/BakaSU", "release.yml:Spoofed-Manager-release",
                                 self.lock["BSU_COMMIT"], "v4.2.0-rc3")])
        self.assertEqual(mu.PENDING_MIRROR[name], data)
        mu.PENDING_MIRROR.clear()

    def test_expired_ci_artifact_keeps_the_mirrored_pin_until_the_tag_moves(self):
        name = "BakaSU-spoofed_ReSukiSU_v4.2.0-rc3_35171-universal-release.apk"
        pinned = mu.write_lock(FULL_LOCK, {"BSU_SPOOFED_APK": name, "BSU_SPOOFED_SHA256": "6" * 64})
        lock = mu.read_lock(pinned)
        rows, updates = plan(lock, {"root-managers"}, fake_lister(lock_text=pinned))  # artifact gone
        self.assertEqual(updates, {})
        self.assertTrue(next(r for r in rows if r[0] == "BakaSU")[-1].startswith("UP TO DATE"))
        bsu_url = mu.PINS["BSU_COMMIT"][2]
        lister = fake_lister({"BSU_COMMIT": NEW}, lock_text=pinned)
        moved = {**lister(bsu_url, options=("--tags",)), "refs/tags/v4.2.0": NEW}

        def moved_lister(url, *patterns, options=()):
            return moved if url == bsu_url and "--tags" in options else lister(url, *patterns, options=options)
        _, updates = plan(lock, {"root-managers"}, moved_lister)
        self.assertEqual(updates["BSU_REF"], "v4.2.0")
        self.assertIsNone(updates["BSU_SPOOFED_APK"])  # the new release has no spoofed build

    def test_ci_artifact_apk_picks_the_tag_push_run_and_the_universal_apk(self):
        commit = "a" * 40
        artifact = io.BytesIO()
        with zipfile.ZipFile(artifact, "w") as archive:
            for abi in ("arm64-v8a", "universal", "x86_64"):
                archive.writestr(f"ReSukiSU_v4.2.0-rc3_35171-{abi}-release.apk", apk_bytes(abi.encode()))
        runs = {"workflow_runs": [
            {"id": 1, "head_sha": commit, "conclusion": "success", "event": "workflow_dispatch",
             "head_branch": "main", "created_at": "2026-09-24"},
            {"id": 2, "head_sha": commit, "conclusion": "success", "event": "push",
             "head_branch": "v4.2.0-rc3", "created_at": "2026-09-23", "html_url": "https://example.invalid/2"},
            {"id": 3, "head_sha": "b" * 40, "conclusion": "success", "event": "push"}]}
        calls = []

        def json_of(path):
            calls.append(path)
            if "/runs?" in path:
                return runs
            run_id = int(path.split("/runs/")[1].split("/")[0])
            return {"artifacts": [{"id": 20 + run_id, "name": "Spoofed-Manager-release", "expired": run_id == 1}]}
        name, data, url = mu.ci_artifact_apk("Baka-SU/BakaSU", "release.yml:Spoofed-Manager-release", commit,
                                             "v4.2.0-rc3", json_of=json_of,
                                             artifact_of=lambda repo, art_id: artifact.getvalue())
        self.assertEqual(name, "ReSukiSU_v4.2.0-rc3_35171-universal-release.apk")
        self.assertEqual(url, "https://example.invalid/2")
        self.assertIn(f"head_sha={commit}", calls[0])
        self.assertIn("/runs/2/artifacts?name=Spoofed-Manager-release", calls[1])  # tag push run first
        with self.assertRaisesRegex(ValueError, "no unexpired"):
            mu.ci_artifact_apk("Baka-SU/BakaSU", "release.yml:Spoofed-Manager-release", "c" * 40, "v1.0.0",
                               json_of=json_of, artifact_of=lambda repo, art_id: b"")

    def test_upload_mirror_creates_the_release_and_never_overwrites(self):
        data = apk_bytes(b"spoofed")
        digest = hashlib.sha256(data).hexdigest()
        created, uploads = [], []

        def json_of(path, method="GET", body=None):
            if method == "POST":
                created.append(body)
                return {"assets": [], "upload_url": "https://uploads.example.invalid/assets{?name,label}"}
            raise urllib.error.HTTPError(path, 404, "Not Found", {}, None)

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def opener(request, timeout=0):
            uploads.append(request.full_url)
            return Response(json.dumps({"id": 1}).encode())
        self.assertEqual(mu.upload_mirror("cogan17/Cogan", {"x.apk": data}, json_of=json_of, opener=opener),
                         ["x.apk"])
        self.assertEqual(created[0]["tag_name"], mu.MIRROR_TAG)
        self.assertTrue(created[0]["prerelease"])
        self.assertEqual(uploads, ["https://uploads.example.invalid/assets?name=x.apk"])
        existing = {"assets": [{"name": "x.apk", "digest": "sha256:" + digest}], "upload_url": "u{?name}"}
        self.assertEqual(mu.upload_mirror("r/r", {"x.apk": data}, json_of=lambda *a, **k: existing), [])
        tampered = {"assets": [{"name": "x.apk", "digest": "sha256:" + "0" * 64}], "upload_url": "u{?name}"}
        with self.assertRaisesRegex(ValueError, "different content"):
            mu.upload_mirror("r/r", {"x.apk": data}, json_of=lambda *a, **k: tampered)

    def test_update_copies_mirror_assets_before_writing_the_lock(self):
        name = "BakaSU-spoofed_ReSukiSU_v4.2.0-rc3_35171-universal-release.apk"
        data = apk_bytes(b"spoofed")
        updates = {"BSU_SPOOFED_APK": name, "BSU_SPOOFED_SHA256": hashlib.sha256(data).hexdigest()}

        def fake_plan(lock, groups):
            mu.PENDING_MIRROR[name] = data
            return [], dict(updates)
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "upstream.lock"
            for upload, expected_status in ((mock.Mock(side_effect=OSError("refused")), 1),
                                            (mock.Mock(return_value=[name]), 0)):
                lock_path.write_text(FULL_LOCK)
                with mock.patch.object(mu, "LOCK", lock_path), mock.patch.object(mu, "plan", fake_plan), \
                        mock.patch.object(mu, "upload_mirror", upload), \
                        mock.patch.object(mu, "collect_fingerprints", lambda: []):
                    status = mu.main(["--mode", "update", "--components", "root-managers"])
                self.assertEqual(status, expected_status)
                self.assertEqual(upload.call_args.args[1], {name: data})
                written = mu.read_lock(lock_path.read_text())
                self.assertEqual(written.get("BSU_SPOOFED_APK"), name if expected_status == 0 else None)
        mu.PENDING_MIRROR.clear()

    def test_new_manager_asset_on_same_tag_is_an_update(self):
        lister = fake_lister()
        assets = lambda repo, tag: [{"name": "KernelSU_v3.3.1_32212-release.apk", "url": "u",
                                     "digest": "sha256:" + "9" * 64}] if repo == "tiann/KernelSU" \
            else fake_assets()(repo, tag)
        _, updates = plan(self.lock, {"root-managers"}, lister, assets_of=assets)
        self.assertEqual(updates, {"KSU_MANAGER_APK": "KernelSU_v3.3.1_32212-release.apk",
                                   "KSU_MANAGER_SHA256": "9" * 64})

    def test_pick_asset_excludes_spoofed_and_debug_and_prefers_release(self):
        assets = [{"name": n, "url": "u", "digest": ""} for n in (
            "KernelSU_Next_v3.4.2_33355-spoofed-release.apk", "KernelSU_Next_v3.4.2_33355-debug.apk",
            "KernelSU_Next_v3.4.2_33355-release.apk", "KernelSU_Next_v3.4.2_33355.apk", "AnyKernel3-x.zip")]
        self.assertEqual(mu.pick_asset(assets, ".apk")["name"], "KernelSU_Next_v3.4.2_33355-release.apk")
        self.assertEqual(mu.pick_asset(assets, ".apk", spoofed=True)["name"],
                         "KernelSU_Next_v3.4.2_33355-spoofed-release.apk")
        # BakaSU v4.2.0-rc3 as published: per-ABI splits plus a universal APK.
        bakasu = [{"name": f"ReSukiSU_v4.2.0-rc3_35171-{abi}-release.apk", "url": "u", "digest": ""}
                  for abi in ("arm64-v8a", "armeabi-v7a", "universal", "x86_64")]
        self.assertEqual(mu.pick_asset(bakasu, ".apk")["name"], "ReSukiSU_v4.2.0-rc3_35171-universal-release.apk")
        with self.assertRaisesRegex(ValueError, "found 2"):
            mu.pick_asset([{"name": "a.apk"}, {"name": "b.apk"}], ".apk")
        with self.assertRaisesRegex(ValueError, "found 0"):
            mu.pick_asset([], ".zip")
        with self.assertRaisesRegex(ValueError, "unsupported asset name"):
            mu.pick_asset([{"name": "bad name.apk"}], ".apk")

    def test_asset_sha256_prefers_the_recorded_digest(self):
        self.assertEqual(mu.asset_sha256({"digest": "sha256:" + "a" * 64, "url": "u"},
                                         opener=lambda *a, **k: self.fail("downloaded")), "a" * 64)

    def test_latest_tag_orders_release_candidates_below_the_final_release(self):
        refs = {f"refs/tags/{t}": t.replace(".", "").replace("-", "").ljust(40, "0")[:40]
                for t in ("v4.1.0", "v4.2.0-rc1", "v4.2.0-rc3", "v4.2.0-rc10", "v4.2.0-beta1")}
        self.assertEqual(mu.latest_tag(refs, allow_rc=True)[0], "v4.2.0-rc10")
        self.assertEqual(mu.latest_tag(refs)[0], "v4.1.0")
        refs["refs/tags/v4.2.0"] = "f" * 40
        self.assertEqual(mu.latest_tag(refs, allow_rc=True), ("v4.2.0", "f" * 40))

    def test_unreachable_upstream_never_becomes_an_update(self):
        def broken(*_args, **_kwargs):
            raise subprocess.TimeoutExpired("git", 40)
        rows, updates = plan(self.lock, set(mu.GROUPS), broken)
        self.assertEqual(updates, {})
        self.assertTrue(all(row[-1].startswith("UNAVAILABLE") for row in rows))

    def test_kernel_advance_moves_auto_and_adds_the_new_sublevel(self):
        lister = fake_lister({"KERNEL_COMMIT_6_1": NEW})
        rows, updates = plan(self.lock, {"kernel-6.1"}, lister, sublevel_of=lambda commit: 178)
        self.assertEqual(updates, {"KERNEL_COMMIT_6_1": NEW, "KERNEL_COMMIT_6_1_178": NEW})
        row = next(row for row in rows if row[0] == "Kernel GKID 6.1")
        self.assertTrue(row[3].startswith("6.1.177 ") and row[4].startswith("6.1.178 "), row)
        updated = mu.read_lock(mu.write_lock(REAL_LOCK, updates))
        self.assertEqual(updated["KERNEL_COMMIT_6_1_177"], self.lock["KERNEL_COMMIT_6_1"])
        self.assertEqual(updated["KERNEL_COMMIT_6_1_178"], NEW)
        self.assertEqual(mu.current_sublevel(updated), 178)

    def test_new_commit_on_same_sublevel_replaces_that_entry(self):
        lister = fake_lister({"KERNEL_COMMIT_6_1": NEW})
        _, updates = plan(self.lock, {"kernel-6.1"}, lister, sublevel_of=lambda commit: 177)
        self.assertEqual(updates, {"KERNEL_COMMIT_6_1": NEW, "KERNEL_COMMIT_6_1_177": NEW})

    def test_unreadable_sublevel_blocks_the_kernel_update(self):
        def unreadable(commit):
            raise OSError("offline")
        rows, updates = plan(self.lock, {"kernel-6.1"}, fake_lister({"KERNEL_COMMIT_6_1": NEW}),
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
        rows, updates = plan(self.lock, {"toolchain"}, fake_lister(neutron=tags),
                                sha256_of=lambda tag: digest)
        self.assertEqual(updates, {"NEUTRON_RELEASE": "01102026", "NEUTRON_SHA256": digest})
        self.assertEqual(mu.read_lock(mu.write_lock(REAL_LOCK, updates))["NEUTRON_RELEASE"], "01102026")
        _, updates = plan(self.lock, {"susfs"}, fake_lister(neutron=tags), sha256_of=lambda tag: digest)
        self.assertEqual(updates, {})  # reported only when toolchain is not selected

    def test_unreadable_toolchain_archive_blocks_the_update(self):
        def broken(tag):
            raise OSError("offline")
        rows, updates = plan(self.lock, {"toolchain"},
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

    def test_release_tags_and_companion_assets_load(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "upstream.lock"
            lock.write_text(FULL_LOCK)
            script = (f'set -eo pipefail; WORKDIR="{ROOT}"; source "{ROOT}/functions.sh" >/dev/null; '
                      f'load_upstream_lock "{lock}" && echo "$PIN_BSU_REF $PIN_KSUN_MANAGER_APK $PIN_NOMOUNT_MODULE_ZIP"')
            result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.split()[-3:], [COMPANION_FIXTURE["BSU_REF"],
                                                      COMPANION_FIXTURE["KSUN_MANAGER_APK"],
                                                      COMPANION_FIXTURE["NOMOUNT_MODULE_ZIP"]])
        for bad in ("KSU_MANAGER_APK=evil;rm -rf.apk", "KSU_MANAGER_APK=../x.apk", "KSU_REF=v1.2.3-beta"):
            self.assertNotEqual(self.load(REAL_LOCK + bad + "\n").returncode, 0, bad)

    def test_branch_name_instead_of_commit_rejected(self):
        result = self.load(REAL_LOCK.replace("BSU_COMMIT=", "BSU_COMMIT=main\n#", 1))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Malformed upstream lock line", result.stdout + result.stderr)

    def test_build_script_reads_every_pin_from_the_lock(self):
        build = (ROOT / "build.sh").read_text()
        self.assertIn('load_upstream_lock "$WORKDIR/configs/upstream.lock" || exit 1', build)
        for name in ("PIN_KSU_COMMIT", "PIN_BSU_COMMIT", "PIN_KSUN_REF", "PIN_KSUN_COMMIT",
                     "PIN_NOMOUNT_COMMIT", "PIN_ANYKERNEL_COMMIT", "PIN_BBG_COMMIT",
                     "PIN_KERNEL_COMMIT_6_1"):
            self.assertIn("$" + name, build, name)
        self.assertNotIn("refs/heads/dev/kernel/setup.sh", build)
        # NoMount installer and source come from the same release tag.
        self.assertIn("nomount/$PIN_NOMOUNT_COMMIT/kernel/setup.sh", build)
        self.assertNotIn("NOMOUNT_SETUP_COMMIT", build + REAL_LOCK)
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
        self.assertNotEqual(run("6.6", "lts").returncode, 0)  # kernel version is locked to 6.1

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
