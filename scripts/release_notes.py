#!/usr/bin/env python3
"""Component versions for the notes of a Manual Release.

Reads the build-env-*.txt files of the source run (what each build really
installed: kernel commit, root manager checkout, SUSFS, features, compiler)
and the pins of the source commit (configs/upstream.lock and, for KSUN+SUSFS,
configs/ksun-susfs-6.1-features.lock.json, whose BBG and NoMount differ from
the other variants). Prints one Markdown section per build variant, with the
root manager APK of the same release so users install a matching manager.

Builds made before KERNEL_FEATURES was saved still get every line; BBG and
NoMount are then marked "if enabled" because the build did not record them.
With --files, a table of the attached files (1-KERNEL_, 2-MANAGER_, ...) comes first.

"What's new" comes from docs/whats-new/<tag>.md when that file exists ("### Baru" /
"### Diperbaiki" headings with "- " items), else from the "Baru: ..." and
"Diperbaiki: ..." lines of the commit messages since the previous release
(--commit-log). --telegram-out writes the same news as short plain text to paste
into Telegram (no links, no Markdown).

Usage: release_notes.py --lock FILE --features-lock FILE --source-sha SHA
           --repo OWNER/NAME --env-dir DIR [--files DIR] [--whats-new-file FILE]
           [--commit-log FILE] [--title T --release-type R --telegram-out FILE]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cogan_manual_update as mu  # noqa: E402
import prepare_downloads as pd  # noqa: E402

SAFE = re.compile(r"[A-Za-z0-9 ._+()/,:-]+")
HEX = re.compile(r"[0-9a-f]{40}")


def read_values(text):
    """KEY=VALUE lines; comments and blank lines ignored, unsafe values dropped."""
    values = {}
    for line in text.splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if SAFE.fullmatch(value.strip()):
                values[key.strip()] = value.strip()
    return values


def short(value):
    return value[:8] if HEX.fullmatch(value or "") else value


def pinned(ref, commit):
    """"v2.1.1 (`7046c7ad`)"; a ref that is itself a commit is not repeated."""
    if ref and commit and not HEX.fullmatch(ref):
        return f"{ref} (`{short(commit)}`)"
    return f"`{short(commit)}`" if commit else "—"


def feature_commit(features_lock, name):
    for feature in features_lock.get("features", []):
        if feature.get("name") == name and HEX.fullmatch(str(feature.get("commit", ""))):
            return feature["commit"]
    return ""


def asset_link(lock, pin_key, companion, repo):
    """Markdown link to a pinned release asset (CI-only builds live in this repo's mirror)."""
    name, tag = lock.get(companion.name_key, ""), lock.get(mu.TAG_KEYS[pin_key], "")
    if not (name and tag):
        return ""
    url = (pd.DOWNLOAD.format(repo=repo, tag=mu.MIRROR_TAG, name=name) if companion.ci
           else pd.DOWNLOAD.format(repo=companion.repo, tag=tag, name=name))
    return f"[`{name}`]({url})"


def variant_section(env, lock, features_lock, repo):
    variant = env.get("BUILD_VARIANT", "?")
    linux = env.get("LINUX_VERSION", "?")
    ksu = env.get("KSU", "")
    susfs = env.get("KSU_SUSFS") == "true"
    candidate = ksu == "KSUN" and susfs
    recorded = env.get("KERNEL_FEATURES", "")
    features = [item.strip() for item in recorded.split(",")] if recorded else []
    shown = lambda name: not features or name in features  # noqa: E731
    maybe = "" if features else " (bila aktif / if enabled)"

    lines = [f"### {variant} — Linux {linux}"]
    if features:
        lines.append(f"- Fitur / features: {recorded}")
    kernel = env.get("KERNEL_SOURCE_BRANCH", "")
    source = env.get("KERNEL_SOURCE_REPO", "")
    lines.append(f"- Kernel: {source + ' ' if source else ''}`{short(kernel) or '?'}`"
                 + (" (kandidat beku / frozen candidate)" if candidate else ""))
    if ksu in pd.MANAGERS and env.get("ROOT_MANAGER_REPO"):
        label, pin_key = pd.MANAGERS[ksu]
        ref, commit = env.get("ROOT_MANAGER_REF", ""), env.get("ROOT_MANAGER_SHA", "")
        if HEX.fullmatch(ref) and commit == lock.get(pin_key):
            ref = lock.get(mu.TAG_KEYS[pin_key], "")  # KernelSU and BakaSU record the commit as ref
        lines.append(f"- Root: {env['ROOT_MANAGER_REPO']} {pinned(ref, commit)}")
        links = [link for link in (asset_link(lock, pin_key, c, repo) for c in mu.COMPANIONS[pin_key]) if link]
        if links:
            note = (" — fork pershoot menerima manager KSUN resmi, diuji di Xiaomi 14T Pro / "
                    "the pershoot fork accepts the official KSUN manager, tested on Xiaomi 14T Pro"
                    if candidate else "")
            lines.append(f"- Manager {label} {lock.get(mu.TAG_KEYS[pin_key], '')}: "
                         + " · ".join(links) + note)
    if susfs and shown("SUSFS"):
        version = env.get("SUSFS_VERSION", "")
        lines.append(f"- SUSFS: {version + ' ' if version else ''}`{short(env.get('SUSFS_SHA', '')) or '?'}`")
    if shown("NoMount"):
        commit = feature_commit(features_lock, "nomount") if candidate else lock.get("NOMOUNT_COMMIT", "")
        same = commit == lock.get("NOMOUNT_COMMIT")
        line = f"- NoMount{maybe}: {pinned(lock.get('NOMOUNT_REF', '') if same else '', commit)}"
        module = asset_link(lock, "NOMOUNT_COMMIT", mu.COMPANIONS["NOMOUNT_COMMIT"][0], repo) if same else ""
        lines.append(line + (f" · modul / module {module}" if module else ""))
    if shown("BBG"):
        commit = feature_commit(features_lock, "bbg") if candidate else lock.get("BBG_COMMIT", "")
        lines.append(f"- BBG{maybe}: {pinned('', commit)}")
    lines.append(f"- AnyKernel3: {pinned('', lock.get('ANYKERNEL_COMMIT', ''))}")
    compiler = env.get("COMPILER_STRING", "")
    neutron = lock.get("NEUTRON_RELEASE", "")
    if compiler or neutron:
        lines.append(f"- Compiler: {compiler or 'Neutron Clang'}"
                     + (f" (rilis / release {neutron})" if neutron and neutron not in compiler else ""))
    return lines


# Numbered downloads of a build (prepare_downloads.py) -> what the file is, how to use it.
FILE_ROLES = (
    ("1-KERNEL_", "Kernel (ZIP AnyKernel3)", "Flash dengan / with **Kernel Flasher**"),
    ("2-MANAGER_", "Root manager resmi, rilis sama dengan kernel / official manager, same release",
     "Install APK"),
    ("3-MANAGER-SPOOFED_", "Manager yang sama, nama paket acak / same manager, random package name",
     "Install APK"),
    ("4-NOMOUNT-MODULE_", "Modul / module NoMount", "Pasang di manager → Modul / install in manager → Modules"),
    ("checksums.txt", "SHA256 semua file / of every file", "Cocokkan sebelum flash / check before flashing"),
)


def files_section(names):
    """Table of the attached files, same order and roles as the build summary."""
    rows = []
    spoofed = any(name.startswith("3-MANAGER-SPOOFED_") for name in names)
    for name in sorted(names):
        role = next((r for r in FILE_ROLES if name.startswith(r[0])), None)
        if not role or not SAFE.fullmatch(name):
            continue
        how = role[2] + (" (pilih 2 **atau** 3 / pick 2 **or** 3)" if spoofed and role[0][0] in "23" else "")
        rows.append(f"| `{name}` | {role[1]} | {how} |")
    if not rows:
        return []
    return ["## Isi rilis / Release files", "", "| File | Isi / What | Cara pakai / How |", "|---|---|---|",
            *rows, ""]


KINDS = ("Baru", "Diperbaiki")
NEWS_LINE = re.compile(r"(Baru|Diperbaiki):\s*(\S.*)")
MAX_ITEMS = 8  # per kind: the news stays short


def whats_new(override_text="", commit_log=""):
    """{"Baru": [...], "Diperbaiki": [...]}: the per-release file wins over commit lines."""
    found = []
    if override_text:
        kind = None
        for line in override_text.splitlines():
            heading = re.fullmatch(r"#+\s*(Baru|Diperbaiki)\s*", line.strip())
            if heading:
                kind = heading.group(1)
            elif kind and line.strip().startswith("- "):
                found.append((kind, line.strip()[2:]))
    else:
        found = [match.groups() for match in map(NEWS_LINE.fullmatch, map(str.strip, commit_log.splitlines()))
                 if match]
    items = {kind: [] for kind in KINDS}
    for kind, text in found:
        text = " ".join(text.split())[:160]
        if text and text not in items[kind] and len(items[kind]) < MAX_ITEMS:
            items[kind].append(text)
    return items


def whats_new_section(items):
    if not any(items.values()):
        return []
    lines = ["## Yang baru / What's new", ""]
    for kind, icon in zip(KINDS, ("✨", "🔧")):
        if items[kind]:
            lines += [f"**{icon} {kind}**", *[f"- {text}" for text in items[kind]], ""]
    return lines


def variant_label(env):
    root = {"KSUN": "KernelSU Next", "KSU": "KernelSU", "BSU": "BakaSU"}.get(env.get("KSU", ""), "Vanilla")
    return root + (" + SUSFS" if env.get("KSU_SUSFS") == "true" else "")


def telegram_text(title, release_type, envs, names, items):
    """Short plain text for Telegram: no links and no Markdown, so it pastes as is."""
    kind_label = {"Draft": "Draft", "Pre-release": "Pre-release", "Release": "Rilis"}.get(release_type, release_type)
    lines = [f"🚀 {title} ({kind_label})"]
    for env in envs:
        lines.append(f"🐧 Linux {env.get('LINUX_VERSION', '?')} • {variant_label(env)}")
        if env.get("KERNEL_FEATURES"):
            lines.append(f"⚙️ {env['KERNEL_FEATURES']}")
    for kind, icon in zip(KINDS, ("✨", "🔧")):
        if items[kind]:
            lines += ["", f"{icon} {kind}", *[f"• {text.replace('`', '')}" for text in items[kind]]]
    pretty = lambda name, prefix: re.sub(r"\.(zip|apk)$", "", name[len(prefix):]).replace("_", " ")  # noqa: E731
    files = []
    for name in sorted(names):
        if name.startswith("1-KERNEL_"):
            files.append("1️⃣ Kernel → flash dengan Kernel Flasher")
        elif name.startswith("2-MANAGER_"):
            files.append(f"2️⃣ Manager {pretty(name, '2-MANAGER_')}")
        elif name.startswith("3-MANAGER-SPOOFED_"):
            files.append(f"3️⃣ Manager spoofed {pretty(name, '3-MANAGER-SPOOFED_')} (pilih 2 atau 3)")
        elif name.startswith("4-NOMOUNT-MODULE_"):
            files.append(f"4️⃣ Modul NoMount {pretty(name, '4-NOMOUNT-MODULE_')}")
    if files:
        lines += ["", "📦 Isi rilis", *files]
    lines += ["", "⚠️ Simpan boot.img stock sebelum flash.", "📥 GitHub cogan17/Cogan → Releases"]
    return "\n".join(lines) + "\n"


def notes(envs, lock, features_lock, source_sha, repo, names=(), items=None):
    lines = whats_new_section(items or {kind: [] for kind in KINDS}) + files_section(names)
    # Component versions are for those who want them: folded, so the page stays short.
    lines += ["<details>", "<summary>Versi komponen / Component versions</summary>", ""]
    for env in envs:
        lines += variant_section(env, lock, features_lock, repo) + [""]
    lines.append(f"Pin dari / pins from `configs/upstream.lock` @ `{short(source_sha)}`; "
                 "naik versi hanya lewat / updated only via **Cogan Manual Update**.")
    lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--features-lock", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--env-dir", type=Path, required=True)
    parser.add_argument("--files", type=Path, help="directory of the files attached to the release")
    parser.add_argument("--whats-new-file", type=Path, help="per-release news; used when it exists")
    parser.add_argument("--commit-log", type=Path, help="commit messages since the previous release")
    parser.add_argument("--title", default="")
    parser.add_argument("--release-type", default="")
    parser.add_argument("--telegram-out", type=Path)
    args = parser.parse_args(argv)
    if not HEX.fullmatch(args.source_sha) or not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repo):
        print("bad --source-sha or --repo", file=sys.stderr)
        return 1
    try:
        lock = read_values(args.lock.read_text(encoding="utf-8"))
        features_lock = json.loads(args.features_lock.read_text(encoding="utf-8"))
        files = sorted(args.env_dir.rglob("build-env-*.txt"))
        envs = [read_values(path.read_text(encoding="utf-8")) for path in files]
        names = [path.name for path in args.files.iterdir()] if args.files else []
        override = (args.whats_new_file.read_text(encoding="utf-8")
                    if args.whats_new_file and args.whats_new_file.is_file() else "")
        log = (args.commit_log.read_text(encoding="utf-8", errors="replace")
               if args.commit_log and args.commit_log.is_file() else "")
    except (OSError, ValueError) as exc:
        print("release notes inputs unreadable: " + str(exc), file=sys.stderr)
        return 1
    if not envs:
        print("no build-env-*.txt under " + str(args.env_dir), file=sys.stderr)
        return 1
    items = whats_new(override, log)
    sys.stdout.write(notes(envs, lock, features_lock, args.source_sha, args.repo, names, items))
    if args.telegram_out:
        args.telegram_out.write_text(telegram_text(args.title, args.release_type, envs, names, items),
                                     encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
