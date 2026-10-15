#!/usr/bin/env python3

import glob
import os
import re

KERNEL_VERSION_ORDER = ["5.10", "5.15", "6.1", "6.6", "6.12"]


def read_or_default(path, default="*No changelog available*"):
	if os.path.isfile(path):
		return open(path).read().rstrip("\n")
	return default


def slugify(text):
	text = text.lower()
	text = re.sub(r"[^\w\s-]", "", text)
	text = re.sub(r"\s+", "-", text.strip())
	return text


def parse_env_file(path):
	env = {}
	with open(path) as f:
		for line in f:
			line = line.strip()
			if "=" in line:
				key, value = line.split("=", 1)
				if key:
					env[key] = value
	return env


def load_build_envs():
	env_files = sorted(glob.glob("release-artifacts/build-env-*.txt"))
	if not env_files:
		raise SystemExit("ERROR: no build-env-*.txt files found in release-artifacts/")

	all_builds = [parse_env_file(f) for f in env_files]

	shared_env = {}
	for key in ("RELEASE_REPO", "RELEASE", "RELEASE_NAME", "KERNEL_NAME"):
		values = {b[key] for b in all_builds if b.get(key)}
		if not values:
			raise SystemExit(f"ERROR: missing required build-env value: {key}")
		shared_env[key] = sorted(values)[0]

	return all_builds, shared_env


def kernel_versions_present(all_builds):
	present = {b.get("KERNEL_VERSION") for b in all_builds if b.get("KERNEL_VERSION")}
	ordered = [v for v in KERNEL_VERSION_ORDER if v in present]
	ordered += sorted(present - set(ordered))
	return ordered


def variant_zip_name(build):
	"""Reconstruct the exact zip filename build.sh produced for this job."""
	base_name = build.get("BASE_NAME")
	release = build.get("RELEASE")
	linux_version = build.get("LINUX_VERSION")
	if not (base_name and release and linux_version):
		return None
	return f"{base_name}-{release}-{linux_version}.zip"


def variant_link(display_name, filename, repo, tag):
	return f"- [{display_name}](https://github.com/{repo}/releases/download/{tag}/{filename})"


def display_variant_name(build):
	name = build.get("BUILD_VARIANT", "")
	kver = build.get("KERNEL_VERSION", "")
	prefix = f"{kver}-"
	return name[len(prefix):] if name.startswith(prefix) else name


def build_kernel_section(kernel_version, builds, repo, tag, existing_zips, inputs):
	android_release = builds[0].get("ANDROID_RELEASE", "unknown")
	label = f"Android{android_release}-{kernel_version}-LTS"
	anchor_title = f"{label} Files"

	representative = next((b for b in builds if b.get("KSU_SUSFS") == "true"), builds[0])

	file_lines = []
	for b in sorted(builds, key=lambda b: display_variant_name(b)):
		zip_name = variant_zip_name(b)
		if zip_name and zip_name in existing_zips:
			file_lines.append(variant_link(display_variant_name(b), zip_name, repo, tag))
	files_block = "\n".join(file_lines) if file_lines else "- *No build artifacts found*"

	susfs_changelog_file = f"release-artifacts/susfs_changelog-{kernel_version}.txt"
	susfs_version = representative.get("SUSFS_VERSION", "Not included")

	anchor_id = slugify(label)
	section = f"""<a name="{anchor_id}"></a>
## {anchor_title}

**Downloads:**
{files_block}

**Build details:**
- Linux version: {representative.get('LINUX_VERSION', 'unknown')}
- Compiler: {representative.get('COMPILER_STRING', 'unknown')}
- SuSFS: {susfs_version}

**SuSFS changelog for this line (last 5 commits):**

{read_or_default(susfs_changelog_file)}
"""
	return label, section


def build_release_body():
	all_builds, shared_env = load_build_envs()
	repo = shared_env["RELEASE_REPO"]
	tag = shared_env["RELEASE"]
	release_name = shared_env["RELEASE_NAME"]

	existing_zips = {os.path.basename(p) for p in glob.glob("release-artifacts/*.zip")}
	versions = kernel_versions_present(all_builds)

	inputs = {
		"nm": os.environ.get("NM_INPUT", ""),
		"droidspaces": os.environ.get("DROIDSPACES_INPUT", ""),
		"lto": os.environ.get("LTO_INPUT", ""),
		"test": os.environ.get("TEST_INPUT", ""),
	}
	status_map = {"true": "Enabled", "false": "Disabled"}
	cap_first = lambda s: s[0].upper() + s[1:] if s else s

	warning = (
		"> [!Warning]\n> This is a test release for pipeline debugging - please do not download or install.\n\n"
		if inputs["test"] == "yes"
		else ""
	)

	toc_entries = []
	sections = []
	for kv in versions:
		builds_for_version = [b for b in all_builds if b.get("KERNEL_VERSION") == kv]
		label, section = build_kernel_section(kv, builds_for_version, repo, tag, existing_zips, inputs)
		toc_entries.append(f"- [{label}](#{slugify(label)})")
		sections.append(section)

	toc_block = "\n".join(toc_entries)
	sections_block = "\n\n---\n\n".join(sections)

	body = f"""{warning}### {release_name}

> [!CAUTION]
> 🇮🇩 Flash dengan risiko sendiri. Simpan `boot.img` stock **sebelum** flash: [Panduan Bootloop](https://github.com/{repo}/blob/HEAD/docs/bootloop.md).
> 🇬🇧 Flash at your own risk. Keep your stock `boot.img` **before** flashing: [Bootloop Guide](https://github.com/{repo}/blob/HEAD/docs/bootloop.en.md).

**Run settings:**
- LTO optimizations: {cap_first(inputs['lto']) or 'Unknown'}
- DroidSpaces: {status_map.get(inputs['droidspaces'], 'Disabled')}
- NoMount: {status_map.get(inputs['nm'], 'Disabled')}

> [!Important]
> 🇮🇩 Kernel **GKI 6.1**: untuk perangkat dengan kernel stock `6.1.x-android14`. Pilih sublevel yang sama atau lebih baru dari kernel stock.
> 🇬🇧 **GKI 6.1** kernel: for devices whose stock kernel is `6.1.x-android14`. Pick the same or a newer sublevel than your stock kernel.

## 🧭 Varian / Variants

| Variant | Root | SuSFS | Notes |
|---------|------|-------|-------|
| KernelSU | KernelSU | ❌ | |
| KernelSU+SuSFS | KernelSU | ✅ | |
| KernelSU-Next | KernelSU Next | ❌ | |
| KernelSU-Next+SuSFS+Test | KernelSU Next (pershoot fork) | ✅ | uji / test build only |
| BakaSU+SuSFS | BakaSU | ✅ | |
| Vanilla | ❌ | ❌ | tanpa root / no root |
| Compat+… | (as named) | ✅ | tanpa LTO / no LTO |

Selengkapnya / More: [README (ID)](https://github.com/{repo}#readme) · [README (EN)](https://github.com/{repo}/blob/HEAD/README.en.md)

## Contents
{toc_block}

---

{sections_block}

---

>[!Note]
>- 🇮🇩 **Bootloop?** Flash kembali `boot.img` stock lewat fastboot: [Panduan Bootloop](https://github.com/{repo}/blob/HEAD/docs/bootloop.md).
>- 🇬🇧 **Bootloop?** Flash your stock `boot.img` back with fastboot: [Bootloop Guide](https://github.com/{repo}/blob/HEAD/docs/bootloop.en.md).
>- 🐛 Bug: [Issues](https://github.com/{repo}/issues) (lampirkan bugreport / attach a bug report).

---

**Features**
- KernelSU / KernelSU Next / BakaSU with SUSFS root hiding
- NoMount, Baseband Guard (BBG)
- TCP BBRv3 (default) + Westwood+, FQ, IP Set, IPv6 NAT
- 300Hz timer, MGLRU, zRAM LZ4 + writeback, mq-deadline, F2FS compression, NTSync

---

>[!Tip]
>This kernel includes **TCP BBRv3** (default) and **Westwood+** congestion control algorithms.
>You can switch between them - changes are temporary and reset after reboot.

**Switch to Westwood+ (better for some networks):**
```bash
su -c "sysctl -w net.ipv4.tcp_congestion_control=westwood"
```

**Restore BBRv3 (default):**
```bash
su -c "sysctl -w net.ipv4.tcp_congestion_control=bbr"
```

Test both and use whichever performs better on your network.
> **Note:** to make the change permanent, create a script in `/data/adb/service.d/` with the sysctl command.

---
**NoMount changelog (last 5 commits):**

{read_or_default("release-artifacts/nomount_changelog.txt")}

**Full commit history:** [Browse all commits](https://github.com/maxsteeel/nomount/commits/master)

---
**KernelSU changelog (last 5 commits):**

{read_or_default("release-artifacts/ksu_changelog.txt")}

**Full commit history:** [Browse all commits](https://github.com/tiann/KernelSU/commits/main)

---
**BakaSU changelog (last 5 commits):**

{read_or_default("release-artifacts/BakaSU_changelog.txt")}

**Full commit history:** [Browse all commits](https://github.com/Baka-SU/BakaSU/commits/main)

---
> [!Tip]
> **Checksums:**
> SHA256 checksums for all files in this release are available in [`checksums.txt`](https://github.com/{repo}/releases/download/{tag}/checksums.txt), attached below.
"""
	return body, versions, shared_env, all_builds
	return body, versions, shared_env, all_builds


def export_github_env(versions, shared_env, all_builds):
	github_env = os.environ.get("GITHUB_ENV")
	if not github_env:
		return

	multi_kernel = "true" if len(versions) > 1 else "false"
	with open(github_env, "a") as f:
		f.write(f"RELEASE_REPO={shared_env['RELEASE_REPO']}\n")
		f.write(f"RELEASE={shared_env['RELEASE']}\n")
		f.write(f"RELEASE_NAME={shared_env['RELEASE_NAME']}\n")
		f.write(f"MULTI_KERNEL={multi_kernel}\n")
		f.write(f"KERNEL_VERSIONS={','.join(versions)}\n")
		if len(versions) == 1:
			# Kept for the single-line Telegram caption path.
			single = versions[0]
			build = next(b for b in all_builds if b.get("KERNEL_VERSION") == single)
			f.write(f"KERNEL_VERSION={single}\n")
			f.write(f"ANDROID_RELEASE={build.get('ANDROID_RELEASE', 'unknown')}\n")


def main():
	body, versions, shared_env, all_builds = build_release_body()
	with open("release_body.md", "w") as f:
		f.write(body)
	export_github_env(versions, shared_env, all_builds)
	print(f"[+] release_body.md written for lines: {', '.join(versions)}")


if __name__ == "__main__":
	main()
