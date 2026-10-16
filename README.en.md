<div align="center">

# Cogan Kernel

**GKI 6.1 kernel for Android with KernelSU, KernelSU Next, BakaSU and SUSFS**

[🇮🇩 Bahasa Indonesia](README.md) · **🇬🇧 English**

[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![GKI android14-6.1](https://img.shields.io/badge/GKI-android14--6.1-3DDC84.svg?logo=android&logoColor=white)](#supported-devices)
[![Release](https://img.shields.io/github/v/release/cogan17/Cogan?include_prereleases&filter=v*&label=release)](https://github.com/cogan17/Cogan/releases)

</div>

> [!CAUTION]
> Cogan is not responsible for bricked devices or lost data. By flashing, you take on all the risk. Back up your data and keep your stock `boot.img` **before** flashing. See the **[Bootloop Guide](docs/bootloop.en.md)**.

---

## About

A generic kernel built from GKI 6.1 sources ([GKI-Duchamp-6.1](https://github.com/ahmed-alnassif/GKI-Duchamp-6.1)) with kernel-based root and SUSFS for root hiding. It aims to work on many `android14-6.1` GKI devices, but is not guaranteed to run on every device.

---

## Features

- **KernelSU / KernelSU Next / BakaSU**: kernel-based root
- **SUSFS**: root hiding (sus path, sus mount, sus kstat, sus map, uname and cmdline spoofing, open redirect, symbol hiding)
- **NoMount**: mount metamodule, always included
- **Baseband Guard (BBG)**: blocks unauthorized writes to critical partitions (can be turned off)
- **Networking**: TCP BBRv3 (default; registered as both `bbr` and `bbr3`, so TCP Optimiser detects it), Westwood+, FQ, IP Set, IPv6 NAT (can be turned off)
- **Performance**: 300 Hz timer, MGLRU, zRAM LZ4 + writeback, mq-deadline, F2FS compression, NTSync
- **TMPFS**: xattr and POSIX ACLs
- **Toolchain**: Neutron Clang (pinned version) with Full LTO, Thin LTO or no LTO
- **Pinned components**: the kernel, root managers, SUSFS, NoMount, BBG, AnyKernel3 and the toolchain are pinned to exact commits and are only updated through **Cogan Manual Update**. Root managers and NoMount follow **official release tags**, so the manager APK and NoMount module always match the kernel

---

## Supported devices

- Devices whose stock kernel is **GKI `6.1.x-android14`**. Check *Settings → About phone → Detailed info and specs → Kernel version*.
- Available sublevels: **6.1.160 and newer**; `lts` = the latest sublevel. Pick the **same or a newer** sublevel than your stock kernel.
- The bootloader must be unlocked.

---

## Variants

| Form option | Variant name (ZIP) | Root | SUSFS | Notes |
|---|---|---|---|---|
| KernelSU | `KernelSU` | KernelSU | ❌ | |
| KernelSU + SUSFS | `KernelSU+SuSFS` | KernelSU | ✅ | |
| KernelSU Next | `KernelSU-Next` | KernelSU Next | ❌ | |
| KernelSU Next + SUSFS | `KernelSU-Next+SuSFS` | KernelSU Next (pershoot fork) | ✅ | **Frozen 6.1.177** kernel, Full LTO, BBG enabled. BBRv3 and extra networking are **always on** (the Networking box is ignored) |
| BakaSU + SUSFS | `BakaSU+SuSFS` | BakaSU | ✅ | |
| Vanilla | `Vanilla` | ❌ | ❌ | No root |
| All variants (advanced) | All standard variants + `Vanilla+NoLTO` + `Compat+…` | | | `Compat` has no LTO, for devices that do not boot the standard variants |

---

## Download & install

1. Make sure your stock kernel is `6.1.x-android14` and the bootloader is unlocked.
2. **Keep your stock `boot.img`**, exactly matching your ROM version ([how](docs/bootloop.en.md#1-keep-your-stock-bootimg-before-flashing)).
3. Download the ZIP from **[Releases](https://github.com/cogan17/Cogan/releases)** and check its SHA256 against `checksums.txt`.
4. Flash the AnyKernel3 ZIP with a kernel flasher app on a rooted device, namely [Kernel Flasher](https://github.com/fatalcoder524/KernelFlasher) (fatalcoder524's build), or from a custom recovery. The ZIP can **not** be flashed with `fastboot`; for fastboot, make an `.img` first ([Using CMD](#using-cmd-platform-tools)).
5. Install the manager APK that matches the kernel. It ships with the build artifacts and is linked in the release notes (**Component versions**, next to the kernel, SUSFS, NoMount and BBG versions), or download it from the official release with the same tag: [KernelSU](https://github.com/tiann/KernelSU/releases), [KernelSU Next](https://github.com/KernelSU-Next/KernelSU-Next/releases) or [BakaSU](https://github.com/Baka-SU/BakaSU/releases). Install the NoMount module (ZIP) from the manager's Modules screen.
6. Reboot. If it gets stuck on the logo or keeps restarting, open the **[Bootloop Guide](docs/bootloop.en.md)**.

---

## Bootloop?

Don't panic and **don't factory reset**. Find the cause first:

| Symptom | Cause | Recover | See the log |
|---|---|---|---|
| Hangs or restarts on the **first logo**, no boot animation | **Kernel** | Flash your stock `boot.img` with fastboot ([how](docs/bootloop.en.md#2-recover-from-a-bootloop)) | Once booted: *Developer options → Bug report* or `adb bugreport`, search `LAST KMSG` / `Kernel panic` ([details](docs/bootloop.en.md#bootloop-caused-by-the-kernel)) |
| The **boot animation** loops, or a bootloop after installing a module | Usually a **module** | **Safe mode**: at the first logo, press Volume Down more than 3 times (press-release), then uninstall the module in the manager ([how](docs/bootloop.en.md#kernel-or-module)) | In safe mode: manager → **Settings → Send logs** ([details](docs/bootloop.en.md#bootloop-caused-by-a-module)) |

If safe mode still bootloops, treat it as a kernel problem. The kernel log (pstore) is **overwritten after the next restart**, so collect it right after the phone boots. The full steps, including a section for the **Xiaomi 14T Pro (rothko)**, are in the **[Bootloop Guide](docs/bootloop.en.md)**.

---

## Using CMD (Platform Tools)

Run every command below in **Windows CMD** from the Platform Tools folder. Output files are saved in that folder.

**Setup**

1. Download [SDK Platform-Tools for Windows](https://developer.android.com/tools/releases/platform-tools) and extract it, for example to `C:\platform-tools`.
2. On the phone: *Settings → About phone*, tap **OS version** 7 times, then turn on **USB debugging** in *Developer options*.
3. Open `C:\platform-tools` in File Explorer, type `cmd` in the address bar and press Enter.
4. Connect the phone, run `adb devices` and allow it on the phone. The status must be `device`.
5. For `su` commands: open the root manager → **Superuser** and allow **Shell**.

**Collect logs**

| For | Command |
|---|---|
| Full bug report, including the kernel log of the failed boot (pstore) | `adb bugreport bugreport.zip` |
| Logcat of the current boot | `adb logcat -b all -d > logcat.txt` |
| Live logcat while the boot animation loops (USB debugging must already be authorized) | `adb logcat -b all > logcat-bootloop.txt`, then `Ctrl+C` after about a minute |
| Current kernel log (root) | `adb shell "su -c dmesg" > dmesg.txt` |
| Kernel log of the previous boot / pstore (root) | `adb shell "su -c 'cat /sys/fs/pstore/console-ramoops*'" > ramoops.txt` |
| Check BBRv3 is active (must say `bbr`) | `adb shell "su -c cat /proc/sys/net/ipv4/tcp_congestion_control"` |
| Check BBG is active (must show `baseband_guard version: …`; if empty, reboot and run it right away) | `adb shell "su -c 'dmesg \| grep baseband_guard'"` |
| Check the `bbr3` name for TCP Optimiser | `adb shell "su -c cat /proc/sys/net/ipv4/tcp_available_congestion_control"` |

**Fastboot: recover or install an `.img`**

```bat
adb reboot bootloader
fastboot devices
fastboot flash boot boot-stock.img
fastboot reboot
```

`adb reboot bootloader` only works while the phone is running. During a bootloop, enter fastboot with the buttons (Xiaomi: **Volume Down + Power**). Replace `boot-stock.img` with `cogan-boot.img` to install the Cogan kernel.

**Making `cogan-boot.img` (the Cogan kernel as an `.img`)**

Cogan deliberately does **not** ship a generic `boot.img`. Kernel compression and the *security patch level* differ per phone, and a mismatch can bootloop it. The [official KernelSU guide](https://kernelsu.org/guide/installation.html#patch-boot-image) gives the same warning. The safe way KernelSU recommends is to wrap the Cogan kernel into your own stock `boot.img`, which is exactly what the AnyKernel3 ZIP does.

1. Put these three files in `C:\platform-tools`:
   - `boot-stock.img`, from exactly the same ROM version ([how](docs/bootloop.en.md#1-keep-your-stock-bootimg-before-flashing)),
   - `Image`, taken from inside the Cogan kernel ZIP (`1-KERNEL_…zip`),
   - `libmagiskboot.so` from the [official Magisk](https://github.com/topjohnwu/Magisk/releases) APK: rename `.apk` to `.zip` and take `lib/arm64-v8a/libmagiskboot.so`.
2. With the phone running (any kernel, no root needed), run:

```bat
adb push libmagiskboot.so /data/local/tmp/magiskboot
adb push boot-stock.img /data/local/tmp/
adb push Image /data/local/tmp/
adb shell "cd /data/local/tmp && chmod +x magiskboot && ./magiskboot unpack boot-stock.img && mv -f Image kernel && ./magiskboot repack boot-stock.img cogan-boot.img"
adb pull /data/local/tmp/cogan-boot.img
```

3. Flash it with fastboot as above: `fastboot flash boot cogan-boot.img`.

Keep a `cogan-boot.img` that is known to boot, together with `boot-stock.img`. If a newer kernel misbehaves, just flash the old one back. Make it again after every ROM update (OTA), because the stock `boot.img` changes too. If the phone supports it, `fastboot boot cogan-boot.img` tries the kernel without flashing; many Xiaomi/MediaTek phones do not support it.

---

## Build your own

Open **Actions → Cogan Kernel Builder → Run workflow** in your repository.

| Field | Description |
|---|---|
| Root Manager | The variant to build (see Variants) |
| Build Mode | `Standard Build` |
| LTO Package | Full LTO (default), Thin LTO or no LTO; NoMount is always included |
| Kernel Version | Locked to `6.1` |
| Build Revision | Optional, `r` + digits (e.g. `r9`). Used in the kernel version (`6.1.177-Cogan-r9-…`), the ZIP name, the flasher banner and the release name; when empty, the run number is used. Rebuilding on the same day? Bump the revision (`r10`) so release names do not clash |
| Kernel Sublevel | `lts` = latest, or just the number (e.g. `177`, not `6.1.177`); 6.1.160 and newer |
| Build Time | `N` = real build time, or a fixed time such as `Thu Jan 1 00:00:00 UTC 2026` |
| Networking | BBRv3 and extra networking (enabled by default; always on for KSUN + SUSFS) |
| BBG | Baseband Guard (enabled by default) |

**Build output:** a green run lists numbered artifacts you can download directly (no extraction needed):

| File | What | How to use |
|---|---|---|
| `1-KERNEL_Cogan-6.1.x_<variant>_<release>.zip` | Kernel (AnyKernel3 ZIP) | Flash with Kernel Flasher |
| `2-MANAGER_<root manager>_<version>.apk` | Official root manager, same release tag as the kernel | Install the APK |
| `3-MANAGER-SPOOFED_<root manager>_<version>.apk` | The same manager with a random package name (harder to detect), from the official build of the same tag: KernelSU Next from its release; BakaSU from its tag's Release run, copied to the internal `cogan-mirror` release because Actions artifacts expire | Install **one**: 2 or 3 |
| `4-NOMOUNT-MODULE_<version>.zip` | Official NoMount module, the same version as the NoMount in the kernel | Install in the manager → Modules |

`build-…` and `build-env-…` artifacts are internal; ignore them. The run summary shows the same table with SHA256 values, plus a **Kernel features** line (e.g. `SUSFS, BBRv3 (default), BBG, NoMount, Full LTO`) read from the built config. The same line shows in Kernel Flasher while flashing. **Cogan Manual Update** pins all these versions together. When upstream has something newer (a GKID 6.1 kernel sublevel, SUSFS, a root manager or NoMount), the run summary shows a **🔔 Reminder**: run Cogan Manual Update (`update` → `kernel-6.1`, `susfs`, `root-managers` or `nomount`), then rebuild. The SUSFS reminder only appears on SUSFS variants. The KSUN + SUSFS variant gets no kernel or SUSFS reminder because its kernel is frozen at 6.1.177.

**Updating components:** open **Actions → Cogan Manual Update**.
- `check` only reports versions.
- `update` applies the new versions straight to `dev`.

The build workflow only compiles and never updates components by itself.

---

## Special thanks

- **GKID Kernels and GKI-Duchamp-6.1**: [Ahmed Al-Nassif](https://github.com/ahmed-alnassif) (base project and kernel source)
- **KernelSU**: [tiann](https://github.com/tiann/KernelSU)
- **KernelSU Next**: [KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next)
- **KernelSU Next SUSFS fork**: [pershoot](https://github.com/pershoot/KernelSU-Next)
- **BakaSU**: [Baka-SU](https://github.com/Baka-SU/BakaSU)
- **SUSFS**: [simonpunk](https://gitlab.com/simonpunk/susfs4ksu)
- **NoMount**: [maxsteeel](https://github.com/maxsteeel/nomount)
- **Baseband Guard (BBG)**: [vc-teahouse](https://github.com/vc-teahouse/Baseband-guard)
- **AnyKernel3**: [osm0sis](https://github.com/osm0sis/AnyKernel3) (through [AK3-GKID](https://github.com/ahmed-alnassif/AK3-GKID))
- **Neutron Clang**: [Neutron-Toolchains](https://github.com/Neutron-Toolchains/clang-build-catalogue)
- README layout inspired by [Wild Kernels](https://github.com/WildKernels/GKI_KernelSU_SUSFS)

Found a bug? Open an [Issue](https://github.com/cogan17/Cogan/issues) with logs. See the [Bootloop Guide](docs/bootloop.en.md#4-after-a-successful-boot-collect-logs) for how.

---

## License

[GPL-3.0](LICENSE)
