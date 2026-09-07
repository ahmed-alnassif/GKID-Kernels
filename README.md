# GKID Kernel

<p align="center">
  <img src="docs/banner.png" alt="GKI-Duchamp Banner">
</p>

[![Build Status](https://github.com/ahmed-alnassif/GKI-Duchamp/actions/workflows/build.yml/badge.svg)](https://github.com/ahmed-alnassif/GKI-Duchamp/actions/workflows/build.yml)
[![Latest Release](https://img.shields.io/github/v/release/ahmed-alnassif/GKI-Duchamp?label=Latest%20Release&color=00aa00)](https://github.com/ahmed-alnassif/GKI-Duchamp/releases)
[![Downloads](https://img.shields.io/github/downloads/ahmed-alnassif/GKI-Duchamp/total?label=Downloads&color=00aa00)](https://github.com/ahmed-alnassif/GKI-Duchamp/releases)
[![Group](https://img.shields.io/badge/Telegram-Group-blue.svg?logo=telegram)](https://t.me/ahmed_alnassif_tg)
[![GitHub License](https://img.shields.io/github/license/ahmed-alnassif/GKI-Duchamp?logo=gnu)](/LICENSE)
[![KernelSU](https://img.shields.io/badge/KernelSU-built--in-success)](https://github.com/tiann/KernelSU)
![ReSukiSU](https://img.shields.io/badge/ReSukiSU-built--in-success)
[![KernelSU Next](https://img.shields.io/badge/KernelSU--Next-built--in-success)](https://github.com/KernelSU-Next/KernelSU-Next)
[![Managers](https://img.shields.io/badge/Managers-multiple-success)](https://github.com/ahmed-alnassif/GKI-Duchamp/releases)
[![SUSFS](https://img.shields.io/badge/SUSFS-Integrated-orange)](https://gitlab.com/simonpunk/susfs4ksu)

A feature-rich Generic Kernel Image (GKI) kernel built for the **Poco X6 Pro (Duchamp)** and compatible with any device running a **6.1.x-android14** GKI kernel. Designed to offer maximum flexibility, it provides multiple variants to suit your specific needs, whether you prioritize root management, system integrity, or performance.

> [!Important]
> - This is a **GKI** kernel and not a **custom** kernel!
> - It supports **ALL** devices that shipped with **Linux 6.1.x** and **Android 14** (stock or AOSP)
> - The build pipeline can also target other GKI LTS lines (**5.10, 5.15, 6.6, 6.12, 6.18**) via a `KERNEL_VERSION` build input — see [Supported GKI Kernel Versions](#-supported-gki-kernel-versions) below. **6.1 remains the primary, actually-tested target for the Poco X6 Pro; the other lines are generic AOSP-sourced builds and are less battle-tested.**
> - **If GKID Kernel is useful to you, please consider a donation.** It helps support continued updates, new features, and fixes for reported issues. See [💰 Donations](#-support-this-project) below.

✨ **ReSuSFS** – Your SuSFS Companion

- **[ReSuSFS](https://github.com/ahmed-alnassif/ReSuSFS)** – The simplest way to manage SuSFS on KernelSU. Clean config files, toggle switches, and a built-in script editor for power users.
- **Community:** Join the discussion and get support on [Telegram](https://t.me/ahmed_alnassif_tg).

## ✨ Key Features

*   **⚡ Performance & Efficiency Tweaks:** Extensively optimized for the Poco X6 Pro (and similar 6.1.xx-android14 devices):

    - Timer frequency set to **300Hz** for noticeably lower input lag and snappier feel
    - **Multi-Gen LRU (MGLRU)** enabled for better multitasking and battery efficiency
    - **Optimized memory operations** (memcpy, memcmp, memset) from ARM-optimized-routines for up to 50% faster string/memory handling
    - **3x faster integer square root** reducing CPU time in cpufreq calculations
    - Optimized **zRAM** with LZ4 compression + writeback + tracking for more and faster usable RAM under heavy loads
    - CPU governors: **schedutil + ondemand** for efficient yet responsive scaling
    - **mq-deadline I/O scheduler** tuned for low latency on UFS 4.0 storage
    - Network stack with **TCP BBRv3** + **TCP Westwood+** + **FQ** + **ECN** + **IPv6 HL support** for reduced latency and faster WiFi/mobile data speeds
    - **F2FS** filesystem tuning (reduced GC sleep to 50ms, enlarged fsync blocks, reduced congestion timeout)
    - **ext4** commit age extended to 30s for fewer disk writes
    - **IP Set** full support + **IPv6 NAT** for better tethering and VPN performance
    - **Filesystem Unicode fix** preventing crashes from invalid UTF-8 filenames on vfat/exfat
    - **NTSync driver** for significantly faster Windows games/apps on Winlator & GameHub

*   **🔋 Battery & Power Optimizations:**
    - Freeze timeout reduced from 20s to **1s** for faster deadlock detection
    - Global wakelock timeout capped at **500ms** to prevent infinite battery drain
    - Alarmtimer wakeup minimized using actual timer values instead of hardcoded 2s
    - Excessive s2idle wake attempts eliminated (single wake instead of multiple)
    - PCI PME check interval extended to reduce unnecessary wakeups
    - VFS cache pressure reduced to **50** for better RAM utilization
    - Cache hot buddy disabled for DynamIQ Shared Unit efficiency

*   **🧠 Scheduler & CPU Optimizations:**
    - CPU scan order adjusted for efficient idle core selection
    - Branch prediction hints optimized in cpufreq paths
    - File struct aligned to 8 bytes for better cache performance
    - Clear page aligned to 16 bytes reducing CPU time on page allocation
    - Memory prefetch optimizations for copy operations

*   **🐉 Kali NetHunter:** Full support enabled (monitor mode, packet injection, rtw88 driver). Matching **WirelessKSU** modules are provided for every variant.

*   **🐳 DroidSpaces:** Full kernel support enabled for [DroidSpaces](https://github.com/ravindu644/Droidspaces-OSS) a lightweight container runtime that lets you run real Linux distributions (Ubuntu, Debian, etc.) with proper isolation and init systems (systemd/OpenRC) directly on your Android device.

*   **🔧 Multiple Variants:** Choose the configuration that fits your needs:
    - **Root solutions:** KernelSU, KernelSU Next, ReSukiSU, or Vanilla (no root)
    - **Manager flexibility:** Multiple-Manager variants let you use your preferred manager app
    - **LTO options:** thinLTO builds + dedicated `+NoLTO` / `Compat+NoLTO` variants

*   **🛡️ SUSFS Integration:** Advanced kernel-level hiding and spoofing capabilities (available in dedicated variants)
*   **🔒 Baseband Guard (BBG):** Lightweight LSM that blocks unauthorized writes to critical partitions and device nodes, protecting the baseband and boot chain from tampering

## 🤝 Support This Project

I actively maintain this kernel, ship updates, and respond to feature requests and bug reports. If it's improved your device, here's how you can support that ongoing work:

### 💰 Donations

| Method | Address |
|--------|---------|
| USDT (TRC20) | `TCyghELuquAtoUFdY65iuJSMqJXbYhWidA` |

> [!Warning]
> Only send **USDT on the TRON (TRC20) network** to this address. Other coins or networks will result in permanent loss of funds.

### Other ways to help

*   **Star the Repository:** Give this project a ⭐ on GitHub to help others discover it
*   **Share:** Spread the word in your community, forums, or with fellow Poco X6 Pro users
*   **Report Issues:** Found a bug? Open an issue with detailed logs to help improve stability
*   **Contribute:** Pull requests, suggestions, and constructive feedback are always welcome

## Community

Join the discussion, get support, and stay up to date on GKID and other projects:

- **Telegram Group:** [ahmed_alnassif_tg](https://t.me/ahmed_alnassif_tg)

## 🧩 Recommended Modules for Poco X6 Pro

Enhance your device with these companion modules:

| Module | Description |
|--------|-------------|
| [**GPU Unlocker** (HyperOS Only)](https://github.com/ahmed-alnassif/GPU-Unlocker) | Unlock the Mali-G615 MC6 GPU from 701 MHz to full 1.4 GHz on POCO X6 Pro HyperOS. |
| [**Thermal Manager**  (AOSP Only)](https://github.com/ahmed-alnassif/Thermal-Manager) | Fixes the thermal mode/profile reset issue on Poco X6 Pro. Monitor and force-persist your chosen mode: **Balanced** ⚖️, **Battery Saver** 🔋, **Performance** ⚡, or **Gaming** 🎮. Includes **WebUI** for instant switching, auto battery saver when screen off, and mode persistence after reboot. |
| [**DSP AudioFix**  (AOSP Only)](https://github.com/ahmed-alnassif/DSP-AudioFix) | Simple fix for distorted audio on Poco X6 Pro and similar Xiaomi/MediaTek devices with Awinic smart amps. |

>[!TIP]
>Both modules are designed specifically for Poco X6 Pro hardware quirks and work seamlessly with any GKID kernel variant.

## 🧬 Supported GKI Kernel Versions

Prebuilt kernel images are available for download from the [Releases](https://github.com/ahmed-alnassif/GKID-Kernels/releases) page. Each release targets a specific GKI LTS line:

| `KERNEL_VERSION` | AOSP branch | Android release | Prebuilt availability | Status |
|---|---|---|---|---|
| `6.1` (default) | — | Android 14 | ✅ [Download from Releases](https://github.com/ahmed-alnassif/GKID-Kernels/releases) | ✅ Primary, tested on Poco X6 Pro |
| `5.10` | `android13-5.10` | Android 13 | ✅ [Download from Releases](https://github.com/ahmed-alnassif/GKID-Kernels/releases) | ⚠️ Untested |
| `5.15` | `android14-5.15` | Android 14 | ✅ [Download from Releases](https://github.com/ahmed-alnassif/GKID-Kernels/releases) | ⚠️ Untested |
| `6.6` | `android15-6.6` | Android 15 | ✅ [Download from Releases](https://github.com/ahmed-alnassif/GKID-Kernels/releases) | ⚠️ Untested |
| `6.12` | `android16-6.12` | Android 16 | ✅ [Download from Releases](https://github.com/ahmed-alnassif/GKID-Kernels/releases) | ⚠️ Untested |

## 📱 Compatibility

*   **Primary Device:** Poco X6 Pro (codenamed `duchamp`)
*   **GKI Requirement:** Compatible with any device running a **6.1.xx-android14** kernel
    *(Note: Only tested on the Poco X6 Pro. Please exercise caution on other devices.)*
*   **Other LTS lines:** Download the corresponding release for **5.10/5.15/6.6/6.12 based** devices. These are untested outside CI. Exercise even more caution.

## ⬇️ Downloads
Find the latest builds for all variants in the [Releases](https://github.com/ahmed-alnassif/GKI-Duchamp/releases) section.

## 🐧 Kernel Source
**GitHub:** [ahmed-alnassif/GKI-Duchamp-6.1](https://github.com/ahmed-alnassif/GKI-Duchamp-6.1)
