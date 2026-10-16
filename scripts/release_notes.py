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
(--commit-log). With --title the notes open with one tip box: the build's features
(build-env KERNEL_FEATURES, else the "Features:" line of its kernel ZIP), the
repository highlights (--highlights), the news, and a dropdown with the same text in
plain form for Telegram (no links, no Markdown), also written to --telegram-out.
Indonesian comes first; the box holds an English dropdown ("New:" / "Fixed:" /
"Updated:" commit lines, "### New" / "### Fixed" headings; Indonesian is used where
an English line is missing) and one Telegram dropdown per language (--telegram-en-out).
"⬆️ Diperbarui" lists the components (kernel, manager, SUSFS, NoMount, BBG, Neutron)
whose version differs from the previous release of the same variant; every release
records its versions in a hidden "cogan-components" marker (--previous-notes).

Usage: release_notes.py --lock FILE --features-lock FILE --source-sha SHA
           --repo OWNER/NAME --env-dir DIR [--files DIR] [--whats-new-file FILE]
           [--commit-log FILE] [--highlights FILE] [--previous-notes FILE]
           [--title T --release-type R --telegram-out FILE --telegram-en-out FILE]
"""
import argparse
import json
import re
import sys
import zipfile
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


KINDS = ("Baru", "Diperbaiki", "Diperbarui")
ICONS = {"Baru": "✨", "Diperbaiki": "🔧", "Diperbarui": "⬆️"}
# Per language: the marker words of each kind (commit lines "Baru: ..." / "New: ...", and the
# "### Baru" / "### New" headings of docs/whats-new/<tag>.md) and the labels people read.
WORDS = {"id": {"Baru": "Baru", "Diperbaiki": "Diperbaiki", "Diperbarui": "Diperbarui"},
         "en": {"Baru": "New", "Diperbaiki": "Fixed", "Diperbarui": "Updated"}}
LABELS = {
    "id": {"features": "Fitur unggulan", "telegram": "📋 Salin untuk grup Telegram (Indonesia)",
           "regular": "biasa/spoofed", "nomount": "Modul NoMount", "boot": "⚠️ Simpan boot.img stock sebelum flash.",
           "types": {"Draft": "Draft", "Pre-release": "Pre-release", "Release": "Rilis"}},
    "en": {"features": "Key features", "telegram": "📋 Copy for the Telegram group (English)",
           "regular": "regular/spoofed", "nomount": "NoMount module", "boot": "⚠️ Keep your stock boot.img before flashing.",
           "types": {"Draft": "Draft", "Pre-release": "Pre-release", "Release": "Release"}},
}
MAX_ITEMS = 8  # per kind: the news stays short


def whats_new(override_text="", commit_log="", lang="id"):
    """{"Baru": [...], "Diperbaiki": [...], "Diperbarui": [...]} in one language: the
    per-release file wins over commit lines. English uses New / Fixed / Updated."""
    kind_of = {word: kind for kind, word in WORDS[lang].items()}
    words = "|".join(kind_of)
    found = []
    if override_text:
        kind = None
        for line in override_text.splitlines():
            heading = re.fullmatch(r"#+\s*(\w+)\s*", line.strip())
            if heading:
                kind = kind_of.get(heading.group(1))
            elif kind and line.strip().startswith("- "):
                found.append((kind, line.strip()[2:]))
    else:
        for line in commit_log.splitlines():
            match = re.fullmatch(rf"({words}):\s*(\S.*)", line.strip())
            if match:
                found.append((kind_of[match.group(1)], match.group(2)))
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
    for kind, icon in ICONS.items():
        if items.get(kind):
            lines += [f"**{icon} {kind}**", *[f"- {text}" for text in items[kind]], ""]
    return lines


COMPONENTS_MARK = re.compile(r"<!-- cogan-components: (\{.*?\}) -->")


def components(env, lock, features_lock):
    """Versions users care about, {name: [identity, shown]}, recorded in every release.

    Compared with the previous release of the same variant for "⬆️ Diperbarui"."""
    ksu, susfs = env.get("KSU", ""), env.get("KSU_SUSFS") == "true"
    candidate = ksu == "KSUN" and susfs
    found = {}
    if env.get("LINUX_VERSION"):
        found["Kernel"] = [env["LINUX_VERSION"]] * 2
    if ksu in pd.MANAGERS:
        label, pin_key = pd.MANAGERS[ksu]
        tag = lock.get(mu.TAG_KEYS[pin_key], "")
        if tag:
            found[f"Manager {label}"] = [tag, tag]
    if susfs and HEX.fullmatch(env.get("SUSFS_SHA", "")):
        commit, version = short(env["SUSFS_SHA"]), env.get("SUSFS_VERSION", "")
        found["SUSFS"] = [commit, f"{version} ({commit})" if version else commit]
    nomount = feature_commit(features_lock, "nomount") if candidate else lock.get("NOMOUNT_COMMIT", "")
    if nomount:
        shown = lock.get("NOMOUNT_REF", "") if nomount == lock.get("NOMOUNT_COMMIT") else ""
        found["NoMount"] = [short(nomount), shown or short(nomount)]
    bbg = feature_commit(features_lock, "bbg") if candidate else lock.get("BBG_COMMIT", "")
    if bbg and "BBG" in (env.get("KERNEL_FEATURES") or "BBG"):
        found["Baseband Guard"] = [short(bbg)] * 2
    if lock.get("NEUTRON_RELEASE"):
        found["Neutron Clang"] = [lock["NEUTRON_RELEASE"]] * 2
    return found


def read_previous_components(notes_text):
    """{variant: components} from the hidden marker of the previous release's notes."""
    match = COMPONENTS_MARK.search(notes_text or "")
    try:
        data = json.loads(match.group(1)) if match else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def updates(previous, current):
    """"Kernel 6.1.177 → 6.1.180" for every component whose identity changed."""
    lines = []
    for name, (identity, shown) in current.items():
        old = previous.get(name)
        if isinstance(old, list) and len(old) == 2 and old[0] != identity:
            lines.append(f"{name} {old[1]} → {shown}")
    return lines


def components_marker(by_variant):
    text = json.dumps(by_variant, separators=(",", ":"), ensure_ascii=False)
    return f"<!-- cogan-components: {text} -->" if "--" not in text else ""


def variant_label(env):
    root = {"KSUN": "KernelSU Next", "KSU": "KernelSU", "BSU": "BakaSU"}.get(env.get("KSU", ""), "Vanilla")
    return root + (" + SUSFS" if env.get("KSU_SUSFS") == "true" else "")


FEATURES_LINE = re.compile(r'^ui_print "Features: ([A-Za-z0-9][A-Za-z0-9 ,._+()-]*)"$', re.MULTILINE)


def features_from_zip(path):
    """The "Features: ..." line brand_anykernel.py wrote into the kernel ZIP's anykernel.sh."""
    try:
        with zipfile.ZipFile(path) as archive:
            match = FEATURES_LINE.search(archive.read("anykernel.sh").decode("utf-8", "replace"))
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    return match.group(1) if match else ""


FEATURE_TEXT = {
    "id": {"SUSFS": "🛡️ SUSFS: sembunyikan root dari aplikasi", "BBR": "internet lebih cepat & stabil",
           "BBG": "🔒 Baseband Guard: lindungi partisi penting", "NoMount": "🧩 NoMount: metamodul tanpa mount",
           "LTO": "kernel lebih ringkas & efisien", "also": "juga "},
    "en": {"SUSFS": "🛡️ SUSFS: hides root from apps", "BBR": "faster, steadier internet",
           "BBG": "🔒 Baseband Guard: protects critical partitions", "NoMount": "🧩 NoMount: mountless metamodule",
           "LTO": "leaner, more efficient kernel", "also": "also "},
}


def feature_items(features, lang="id"):
    """Friendly lines for the build's own feature list (scripts/kernel_features.py)."""
    text, items = FEATURE_TEXT[lang], []
    for token in (t.strip() for t in re.split(r",(?![^()]*\))", features or "")):
        if token in ("SUSFS", "BBG", "NoMount"):
            items.append(text[token])
        elif token.startswith("BBR"):
            items.append(f"🚀 {token.replace('also ', text['also'])}: {text['BBR']}")
        elif token in ("Full LTO", "Thin LTO"):
            items.append(f"⚡ {token}: {text['LTO']}")
    return items


def read_highlights(text, lang="id"):
    """Repository highlights true for every build: "- " lines of docs/whats-new/highlights.md,
    under "### Indonesia" or "### English" (lines before any heading are Indonesian)."""
    section, found = "id", {"id": [], "en": []}
    for line in (text or "").splitlines():
        heading = re.fullmatch(r"#+\s*(Indonesia|English)\s*", line.strip())
        if heading:
            section = "id" if heading.group(1) == "Indonesia" else "en"
        elif line.strip().startswith("- "):
            found[section].append(line.strip()[2:].strip())
    return (found[lang] or found["id"])[:4]


def plain(text):
    return text.replace("`", "").replace("**", "")


def telegram_text(title, release_type, envs, names, items, features=(), highlights=(), lang="id"):
    """Short plain text for Telegram: no links and no Markdown, so it pastes as is."""
    label = LABELS[lang]
    lines = [f"🚀 {title} ({label['types'].get(release_type, release_type)})"]
    lines += [f"🐧 Linux {env.get('LINUX_VERSION', '?')} • {variant_label(env)}" for env in envs]
    best = [*features, *highlights]
    if best:
        lines += ["", f"⭐ {label['features']}", *[f"• {plain(text)}" for text in best]]
    for kind, icon in ICONS.items():
        if items.get(kind):
            lines += ["", f"{icon} {WORDS[lang][kind]}", *[f"• {plain(text)}" for text in items[kind]]]
    parts = []
    if any(name.startswith("1-KERNEL_") for name in names):
        parts.append("Kernel")
    managers = sorted(name for name in names if name.startswith(("2-MANAGER_", "3-MANAGER-SPOOFED_")))
    if managers:
        manager = re.sub(r"\.apk$", "", managers[0].split("_", 1)[1]).replace("_", " ")
        parts.append(f"Manager {manager}" + (f" ({label['regular']})" if len(managers) > 1 else ""))
    nomount = [name for name in names if name.startswith("4-NOMOUNT-MODULE_")]
    if nomount:
        version = re.sub(r"\.zip$", "", nomount[0][len("4-NOMOUNT-MODULE_"):]).split("_")[0]
        parts.append(f"{label['nomount']} {version}")
    if parts:
        lines += ["", "📦 " + " + ".join(parts)]
    lines += [label["boot"], "📥 GitHub cogan17/Cogan → Releases"]
    return "\n".join(lines) + "\n"


def box_content(title, envs, features, highlights, items, lang):
    """Title, features and news of the release box in one language (Markdown lines)."""
    lines = [f"**⭐ {title}** · " + " · ".join(f"Linux {env.get('LINUX_VERSION', '?')} · {variant_label(env)}"
                                            for env in envs), ""]
    best = [*features, *highlights]
    if best:
        lines += [f"**{LABELS[lang]['features']}**", *[f"- {text}" for text in best], ""]
    for kind, icon in ICONS.items():
        if items.get(kind):
            lines += [f"**{icon} {WORDS[lang][kind]}**", *[f"- {text}" for text in items[kind]], ""]
    return lines


def dropdown(summary, lines):
    return ["<details>", f"<summary>{summary}</summary>", "", *lines, "</details>", ""]


def frame(title, envs, content):
    """One GitHub tip box: Indonesian first, then dropdowns with the English version and the
    Telegram texts. content: {"id"|"en": {"features", "highlights", "items", "telegram"}}."""
    body = box_content(title, envs, content["id"]["features"], content["id"]["highlights"],
                       content["id"]["items"], "id")
    english = box_content(title, envs, content["en"]["features"], content["en"]["highlights"],
                          content["en"]["items"], "en")
    body += dropdown("🇬🇧 English", english)
    for lang in ("id", "en"):
        body += dropdown(LABELS[lang]["telegram"],
                         ["```text", *content[lang]["telegram"].rstrip("\n").splitlines(), "```", ""])
    while body and not body[-1]:
        body.pop()
    return ["> [!TIP]", *[f"> {line}" if line else ">" for line in body], ""]


def notes(envs, lock, features_lock, source_sha, repo, names=(), items=None, top=None, marker=""):
    """top: the frame lines; without it the news section stands alone (older callers).
    marker: the hidden component record the next release compares against."""
    news = top if top is not None else whats_new_section(items or {kind: [] for kind in KINDS})
    lines = news + files_section(names)
    # Component versions are for those who want them: folded, so the page stays short.
    lines += ["<details>", "<summary>Versi komponen / Component versions</summary>", ""]
    for env in envs:
        lines += variant_section(env, lock, features_lock, repo) + [""]
    lines.append(f"Pin dari / pins from `configs/upstream.lock` @ `{short(source_sha)}`; "
                 "naik versi hanya lewat / updated only via **Cogan Manual Update**.")
    lines += ["", "</details>"]
    if marker:
        lines += ["", marker]
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
    parser.add_argument("--telegram-out", type=Path, help="Indonesian Telegram text")
    parser.add_argument("--telegram-en-out", type=Path, help="English Telegram text")
    parser.add_argument("--highlights", type=Path, help="repository highlights (docs/whats-new/highlights.md)")
    parser.add_argument("--previous-notes", type=Path, help="notes of the previous release (component marker)")
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
        highlights_text = (args.highlights.read_text(encoding="utf-8")
                           if args.highlights and args.highlights.is_file() else "")
        kernels = sorted(p for p in args.files.iterdir() if p.name.startswith("1-KERNEL_")) if args.files else []
        previous = read_previous_components(args.previous_notes.read_text(encoding="utf-8", errors="replace")
                                            if args.previous_notes and args.previous_notes.is_file() else "")
    except (OSError, ValueError) as exc:
        print("release notes inputs unreadable: " + str(exc), file=sys.stderr)
        return 1
    if not envs:
        print("no build-env-*.txt under " + str(args.env_dir), file=sys.stderr)
        return 1
    items = whats_new(override, log)
    english = whats_new(override, log, "en")
    for kind in KINDS:  # an item without its English line still shows, in Indonesian
        english[kind] = english[kind] or items[kind]
    # The build's own features: saved in build-env since PR #66, else read from its kernel ZIP.
    recorded_features = []
    for env in envs:
        recorded = env.get("KERNEL_FEATURES", "")
        if not recorded:
            match = [k for k in kernels if len(kernels) == 1 or k.stem.endswith("_" + env.get("BUILD_VARIANT", "?"))]
            recorded = features_from_zip(match[0]) if match else ""
        recorded_features.append(recorded)
    # "⬆️ Diperbarui": component versions against the previous release of the same variant.
    current = {env.get("BUILD_VARIANT", "?"): components(env, lock, features_lock) for env in envs}
    automatic = [line for variant, found in current.items() for line in updates(previous.get(variant, {}), found)]
    items["Diperbarui"] = list(dict.fromkeys(automatic + items["Diperbarui"]))[:MAX_ITEMS]
    english["Diperbarui"] = list(dict.fromkeys(automatic + english["Diperbarui"]))[:MAX_ITEMS]
    top = None
    if args.title:
        content = {}
        for lang, news in (("id", items), ("en", english)):
            features = list(dict.fromkeys(f for recorded in recorded_features for f in feature_items(recorded, lang)))
            highlights = read_highlights(highlights_text, lang)
            content[lang] = {"features": features, "highlights": highlights, "items": news,
                             "telegram": telegram_text(args.title, args.release_type, envs, names, news,
                                                       features, highlights, lang)}
        top = frame(args.title, envs, content)
        for lang, out in (("id", args.telegram_out), ("en", args.telegram_en_out)):
            if out:
                out.write_text(content[lang]["telegram"], encoding="utf-8")
    sys.stdout.write(notes(envs, lock, features_lock, args.source_sha, args.repo, names, items, top,
                           components_marker(current)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
