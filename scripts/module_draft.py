#!/usr/bin/env python3
"""Keep one draft release per KernelSU module in modules/ (owner 2026-10-17: "Jika modul selesai
tolong kamu simpan di repo cogan sebagai draft").

For each module: pack the ZIP (scripts/package_module.py), then
- a published release with the same tag already exists -> leave it (bump the version to make a new draft);
- a draft with the same tag and the same ZIP (SHA256 in its notes) exists -> nothing to do;
- otherwise -> delete this module's older drafts and create a new draft with the ZIP.

Tags are "<folder>-<version>", e.g. "thermal-monitor-v1.1": never "v...", so the kernel release
tooling (Manual Release, the README badge) never mistakes a module for a kernel release.
Drafts have no git tag yet; the tag is made when the owner publishes.

Usage: module_draft.py --repo OWNER/NAME --sha COMMIT [--only FOLDER|semua] [--out DIR] [--summary FILE]
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import package_module  # noqa: E402

MARK = "cogan-module:"


def gh(*args, capture=True):
    result = subprocess.run(["gh", *args], capture_output=capture, text=True)
    if result.returncode:
        raise SystemExit(f"gh {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def intro(readme):
    """First plain paragraph of a module README (after the title and the language link)."""
    for block in readme.read_text().split("\n\n"):
        block = block.strip()
        if block and not block.startswith(("#", "[")):
            return " ".join(block.split())
    return ""


def notes(folder, title, zip_name, digest, repo, sha):
    base = f"https://github.com/{repo}/blob/{sha}/modules/{folder}"
    module = ROOT / "modules" / folder
    return f"""> [!NOTE]
> **Draft modul, belum dirilis.** Uji dulu di HP. Untuk merilis: buka draft ini → **Edit** → **Publish release**, dan hilangkan centang *Set as the latest release* agar rilis kernel tetap yang terbaru.

### {title}

{intro(module / "README.md")}

**Pasang:** manager KernelSU / KernelSU Next / BakaSU (atau Magisk) → Modul → pasang ZIP → reboot. Panduan: [README]({base}/README.md)

<details>
<summary>🇬🇧 English</summary>

**Module draft, not released yet.** Test it on a phone first. To release: open this draft → **Edit** → **Publish release**, and untick *Set as the latest release* so the kernel release stays the latest.

{intro(module / "README.en.md")}

**Install:** KernelSU / KernelSU Next / BakaSU manager (or Magisk) → Modules → install the ZIP → reboot. Guide: [README]({base}/README.en.md)

</details>

| File | SHA256 |
|---|---|
| `{zip_name}` | `{digest}` |

Sumber / Source: [`{sha[:12]}`](https://github.com/{repo}/commit/{sha})

<!-- {MARK} {folder} {digest} -->
"""


def releases(repo):
    out = gh("api", "--paginate", f"repos/{repo}/releases?per_page=100",
             "--jq", ".[] | {id, tag_name, draft, body} | tojson")
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def draft_module(folder, repo, sha, out, existing):
    module = ROOT / "modules" / folder
    prop = package_module.read_prop(module / "module.prop")
    title = f"{prop['name']} {prop['version']}"
    tag = f"{folder}-{prop['version']}"
    target = package_module.package(module, out)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    mine = [r for r in existing if r["tag_name"].startswith(f"{folder}-v")]
    if any(r["tag_name"] == tag and not r["draft"] for r in mine):
        return tag, "sudah dirilis, naikkan versi untuk draft baru"
    if any(r["tag_name"] == tag and r["draft"] and f"{MARK} {folder} {digest}" in (r["body"] or "") for r in mine):
        return tag, "draft sudah terbaru"
    for release in mine:
        if release["draft"]:
            gh("api", "-X", "DELETE", f"repos/{repo}/releases/{release['id']}")
    notes_file = out / f"{folder}-notes.md"
    notes_file.write_text(notes(folder, title, target.name, digest, repo, sha))
    gh("release", "create", tag, str(target), "--repo", repo, "--draft", "--title", title,
       "--notes-file", str(notes_file), "--target", sha, "--latest=false")
    return tag, "draft dibuat" if not any(r["draft"] for r in mine) else "draft diperbarui"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--only", default="semua")
    parser.add_argument("--out", default="dist")
    parser.add_argument("--summary")
    args = parser.parse_args()
    folders = sorted(p.parent.name for p in (ROOT / "modules").glob("*/module.prop"))
    if args.only != "semua":
        if args.only not in folders:
            raise SystemExit(f"unknown module {args.only!r}; known: {', '.join(folders)}")
        folders = [args.only]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    existing = releases(args.repo)
    rows = [draft_module(folder, args.repo, args.sha, out, existing) for folder in folders]
    lines = ["### Draft modul", "", "| Modul | Hasil |", "|---|---|"]
    lines += [f"| `{tag}` | {result} |" for tag, result in rows]
    lines += ["", f"Draft ada di [Releases](https://github.com/{args.repo}/releases) (hanya terlihat oleh pemilik repo)."]
    text = "\n".join(lines) + "\n"
    print(text)
    if args.summary:
        with open(args.summary, "a") as summary:
            summary.write(text)


if __name__ == "__main__":
    main()
