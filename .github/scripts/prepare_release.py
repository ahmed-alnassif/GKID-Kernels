#!/usr/bin/env python3

import glob
import os


def read_or_default(path, default="*No changelog available*"):
	if os.path.isfile(path):
		return open(path).read().rstrip("\n")
	return default


def load_env_from_builds():
	env_files = sorted(glob.glob("release-artifacts/build-env-*.txt"))
	env_vars = {
		"KSU": "Not included",
		"KSU_SUSFS": "Not included",
		"SUSFS_VERSION": "Not included",
		"KERNEL_VERSION": "6.1",
		"ANDROID_RELEASE": "14",
		"KERNEL_SOURCE_REPO": "ahmed-alnassif/GKI-Duchamp-6.1",
		"KERNEL_SOURCE_BRANCH": "GKID-6.1",
	}

	chosen = None
	for f in env_files:
		print(f"[*] Checking {f}...")
		content = open(f).read()
		if "SUSFS_VERSION=" in content and "KSU_SUSFS=true" in content:
			chosen = f
			print(f"[+] Found SUSFS build: {f}")
			break
	chosen = chosen or (env_files[0] if env_files else None)

	if chosen:
		print(f"[*] Loading environment from: {chosen}")
		for line in open(chosen):
			if "=" in line:
				key, value = line.strip().split("=", 1)
				if key and value:
					env_vars[key] = value

	github_env = os.environ.get("GITHUB_ENV")
	if github_env:
		with open(github_env, "a") as f:
			for k, v in env_vars.items():
				f.write(f"{k}={v}\n")

	return env_vars


def variant_link(variant, repo, tag):
   return f"  - [{variant}](https://github.com/{repo}/releases/download/{tag}/{variant}.zip)"


def build_release_body(env_vars):
	repo = env_vars.get("RELEASE_REPO")
	tag = env_vars.get("RELEASE")

	missing = [k for k in ("RELEASE_REPO", "RELEASE", "RELEASE_NAME", "LINUX_VERSION", "COMPILER_STRING") if not env_vars.get(k)]
	if missing:
		raise SystemExit(f"ERROR: missing required build-env values: {', '.join(missing)}")

	variants = sorted(
		os.path.basename(p)[:-4] for p in glob.glob("release-artifacts/*.zip")
	)
	gkid_variants = "\n".join(
		variant_link(v, repo, tag) for v in variants if "gkid" in v.lower()
	)
	wireless_variants = "\n".join(
		variant_link(v, repo, tag) for v in variants if "wirelessksu" in v.lower()
	)

	status_map = {"true": "Enabled", "false": "Disabled"}
	nh_input = os.environ.get("NH_INPUT", "")
	nm_input = os.environ.get("NM_INPUT", "")
	droidspaces_input = os.environ.get("DROIDSPACES_INPUT", "")
	lto_input = os.environ.get("LTO_INPUT", "")
	test_input = os.environ.get("TEST_INPUT", "")

	warning = (
		">[!warning]\n>This is an empty testing release — please do not download or install!\n\n"
		if test_input == "yes"
		else ""
	)

	kali_module_line = "None" if nh_input != "true" else ""

	cap_first = lambda s: s[0].upper() + s[1:] if s else s
	kernel_version = env_vars["KERNEL_VERSION"]
	android_release = env_vars["ANDROID_RELEASE"]
	kernel_source_repo = env_vars["KERNEL_SOURCE_REPO"]
	kernel_source_branch = env_vars["KERNEL_SOURCE_BRANCH"]
	kernel_version_tag = f"android{android_release}-{kernel_version}-lts"
	changelog_title = f"Android{android_release}-{kernel_version}-LTS"
	changelog_file = f"release-artifacts/android_kernel-{kernel_version}_changelog.txt"
	body = f"""{warning}### ✨ {env_vars['RELEASE_NAME']} ✨

> [!Tip]
> 💰 **Support this project:** If GKID Kernel is useful to you, consider a donation - USDT (TRC20): `TCyghELuquAtoUFdY65iuJSMqJXbYhWidA`. Only send on the TRON network. See the [README](https://github.com/ahmed-alnassif/GKI-Duchamp#-support-this-project) for details.

✨ **ReSuSFS** – Your SuSFS Companion

- **[ReSuSFS](https://github.com/ahmed-alnassif/ReSuSFS)** – The simplest way to manage SuSFS on KernelSU. Clean config files, toggle switches, and a built-in script editor for power users.
- **Community:** Join the discussion and get support on [Telegram](https://t.me/ahmed_alnassif_tg).

**Build Information:**
- 🐧 **Kernel:** {env_vars['RELEASE_NAME']}
- 🔥 **LTO optimizations:** {cap_first(lto_input)}
- 🐉 **Kali NetHunter:** {status_map.get(nh_input, 'Disabled')}
- 🐳 **DroidSpaces:** {status_map.get(droidspaces_input, 'Disabled')}
- 🛡️ **SuSFS:** ඞ {env_vars['SUSFS_VERSION']}
- 🥷 **NoMount:** {status_map.get(nm_input, 'Disabled')}
- 🔖 **Version:** {env_vars['LINUX_VERSION']} ({kernel_version_tag})
- 📦 **Variants:**
{gkid_variants}
- 🐉 **Kali NetHunter KernelSU modules:** {kali_module_line}
{wireless_variants}
- ⚙️ **Compiler:** {env_vars['COMPILER_STRING']}

> [!Important]
> - This is a **GKI** kernel and not a **custom** kernel!
> - It supports **ALL** devices that shipped with **Linux {kernel_version}.x** and **Android {android_release}** (stock or AOSP)

---

>[!Note]
>- **Bootloop?** Flash a **Compat** variant first.
>- **Issues?** Check [Discussions](https://github.com/ahmed-alnassif/GKI-Duchamp/discussions) before opening an issue.

---

### 💬 Community & Support
- **Have questions?** Start a [Discussion](https://github.com/ahmed-alnassif/GKI-Duchamp/discussions)
- **Found a bug?** Open an [Issue](https://github.com/ahmed-alnassif/GKI-Duchamp/issues) with logs
- **Enjoying the kernel?** ⭐ Star the [repo](https://github.com/ahmed-alnassif/GKI-Duchamp)!

---

**⚡ Performance & Battery Optimizations**
Engineered for smoother UI, better multitasking & gaming on Poco X6 Pro:

**⚡ Performance**
- **300Hz timer** → lower input lag, snappier feel
- **MGLRU** → better multitasking & battery life
- **Faster memory ops** → up to 50% faster string/memory handling
- **mq-deadline I/O** → low-latency on UFS 4.0 storage
- **CPU governors:** schedutil + ondemand → efficient & responsive
- **NTSync driver** → faster Windows games/apps on Winlator/GameHub

**🌐 Network**
- **TCP BBRv3 + Westwood+** → better WiFi/mobile data speeds
- **IPv6 NAT + IP Set** → better tethering & VPN

**🔋 Battery Life**
- **Wakelock cap:** 500ms → prevents battery drain
- **Freeze timeout:** 20s → 1s → faster deadlock detection
- **ext4 commit age:** 30s → fewer disk writes
- **Minimized alarm wakeups** → less standby drain

**💾 Storage & Filesystem**
- **F2FS tuning:** reduced GC sleep (50ms) → smoother I/O
- **ext4 optimization** → extended commit age

**🛡️ Security**
- **Baseband Guard (BBG)** → blocks unauthorized writes to critical partitions

---

### 📱 Recommended Companion Modules
Enhance your Poco X6 Pro with these modules designed for GKID kernels:

| Module | Description | ROM |
|--------|-------------|-----|
| [**GPU Unlocker**](https://github.com/ahmed-alnassif/GPU-Unlocker) | Unlock Mali-G615 MC6 from **701MHz → 1.4GHz** (100% boost) | HyperOS |
| [**Thermal Manager**](https://github.com/ahmed-alnassif/Thermal-Manager) | Fix thermal mode reset. Force-persist Balanced ⚖️, Battery Saver 🔋, Performance ⚡, or Gaming 🎮. Includes WebUI. | AOSP |
| [**DSP AudioFix**](https://github.com/ahmed-alnassif/DSP-AudioFix) | Fix distorted audio on devices with Awinic smart amps | AOSP |

> [!Tip]
> **HyperOS users:** GPU Unlocker gives you a massive gaming performance boost.
> **AOSP users:** Thermal Manager fixes a stock bug that resets your thermal mode.

---

>[!Tip]
>This kernel includes **TCP BBRv3** (default) and **Westwood+** congestion control algorithms.
>You can switch between them - **changes are temporary and reset after reboot.**

**Switch to Westwood+ (better for some networks):**
```bash
su -c "sysctl -w net.ipv4.tcp_congestion_control=westwood"
```

**Restore BBRv3 (default):**
```bash
su -c "sysctl -w net.ipv4.tcp_congestion_control=bbr"
```

Test both and choose the one that performs better on your network.
> **Note:** To make the change permanent, create a script in `/data/adb/service.d/` with the sysctl command.

---
**{changelog_title} Kernel Changelog (last 10 commits):**

{read_or_default(changelog_file)}

**Full Commit History:** [Browse all commits](https://github.com/{kernel_source_repo}/commits/{kernel_source_branch})

---
**SuSFS Changelog (last 5 commits):**

{read_or_default("release-artifacts/susfs_changelog.txt")}

**Full Commit History:** [Browse all commits](https://gitlab.com/simonpunk/susfs4ksu)

---
**NoMount Changelog (last 5 commits):**

{read_or_default("release-artifacts/nomount_changelog.txt")}

**Full Commit History:** [Browse all commits](https://github.com/maxsteeel/nomount/commits/master)

---
**KernelSU Changelog (last 5 commits):**

{read_or_default("release-artifacts/ksu_changelog.txt")}

**Full Commit History:** [Browse all commits](https://github.com/tiann/KernelSU/commits/main)

---
**ReSukiSU Changelog (last 5 commits):**

{read_or_default("release-artifacts/ReSukiSU_changelog.txt")}

**Full Commit History:** [Browse all commits](https://github.com/ReSukiSU/ReSukiSU/commits/main)

---
**KernelSU Next Changelog (last 5 commits):**

{read_or_default("release-artifacts/ksun_changelog.txt")}

**Full Commit History:** [Browse all commits](https://github.com/KernelSU-Next/KernelSU-Next/commits/dev)

---
**Checksums:**
```
{open("release-artifacts/checksums.txt").read().rstrip()}
```
"""
	return body


def main():
	env_vars = load_env_from_builds()
	body = build_release_body(env_vars)
	with open("release_body.md", "w") as f:
		f.write(body)
	print("[+] release_body.md written.")


if __name__ == "__main__":
	main()
