<div align="center">

# Cogan Kernel

**GKI 6.1 kernel for Android with KernelSU, KernelSU Next, BakaSU and SUSFS**

[🇮🇩 Bahasa Indonesia](README.md) · **🇬🇧 English**

[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![GKI android14-6.1](https://img.shields.io/badge/GKI-android14--6.1-3DDC84.svg?logo=android&logoColor=white)](#supported-devices)
[![Release](https://img.shields.io/github/v/release/cogan17/Cogan?include_prereleases&label=release)](https://github.com/cogan17/Cogan/releases)

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
- **Networking**: TCP BBRv3 (default), Westwood+, FQ, IP Set, IPv6 NAT (can be turned off)
- **Performance**: 300 Hz timer, MGLRU, zRAM LZ4 + writeback, mq-deadline, F2FS compression, NTSync
- **TMPFS**: xattr and POSIX ACLs
- **Toolchain**: Neutron Clang (pinned version) with Full LTO, Thin LTO or no LTO
- **Pinned components**: the kernel, root managers, SUSFS, NoMount, BBG, AnyKernel3 and the toolchain are pinned to exact commits and are only updated through **Cogan Manual Update**

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
| KernelSU Next + SUSFS (uji) | `KernelSU-Next+SuSFS+Test` | KernelSU Next (pershoot fork) | ✅ | **Test build only**: 6.1.177 (`lts`), Full LTO, BBG enabled |
| BakaSU + SUSFS | `BakaSU+SuSFS` | BakaSU | ✅ | |
| Vanilla | `Vanilla` | ❌ | ❌ | No root |
| All variants (advanced) | All standard variants + `Vanilla+NoLTO` + `Compat+…` | | | `Compat` has no LTO, for devices that do not boot the standard variants |

---

## Download & install

1. Make sure your stock kernel is `6.1.x-android14` and the bootloader is unlocked.
2. **Keep your stock `boot.img`**, exactly matching your ROM version ([how](docs/bootloop.en.md#1-keep-your-stock-bootimg-before-flashing)).
3. Download the ZIP from **[Releases](https://github.com/cogan17/Cogan/releases)** and check its SHA256 against `checksums.txt`.
4. Flash the AnyKernel3 ZIP with a kernel flasher app on a rooted device, for example [Kernel Flasher](https://github.com/capntrips/KernelFlasher) or [Horizon Kernel Flasher](https://github.com/libxzr/HorizonKernelFlasher), or from a custom recovery. The ZIP can **not** be flashed with `fastboot`.
5. Install the matching manager app from its official releases: [KernelSU](https://github.com/tiann/KernelSU/releases), [KernelSU Next](https://github.com/KernelSU-Next/KernelSU-Next/releases) or [BakaSU](https://github.com/Baka-SU/BakaSU/releases).
6. Reboot. If it gets stuck on the logo or keeps restarting, open the **[Bootloop Guide](docs/bootloop.en.md)**.

---

## Bootloop?

Don't panic and **don't factory reset**. Flashing your stock `boot.img` back with fastboot is usually enough. The full steps, including a section for the **Xiaomi 14T Pro (rothko)**, are in the **[Bootloop Guide](docs/bootloop.en.md)**.

---

## Build your own

Open **Actions → Cogan Kernel Builder → Run workflow** in your repository.

| Field | Description |
|---|---|
| Root Manager | The variant to build (see Variants) |
| Build Mode | `Standard Build` |
| LTO Package | Full LTO (default), Thin LTO or no LTO; NoMount is always included |
| Kernel Version | Locked to `6.1` |
| Build Revision | Optional, `r` + digits (e.g. `r9`), added to the release name |
| Kernel Sublevel | `lts` = latest, or just the number (e.g. `177`, not `6.1.177`); 6.1.160 and newer |
| Build Time | `N` = real build time, or a fixed time such as `Thu Jan 1 00:00:00 UTC 2026` |
| Networking | BBRv3 and extra networking (enabled by default) |
| BBG | Baseband Guard (enabled by default) |

**Build output:** on the run page, download the `Cogan-<variant>-….zip` artifact. It is the flashable AnyKernel3 ZIP itself (no extraction needed), and its SHA256 is shown in the run summary.

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
