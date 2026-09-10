# GKID Kernel

<p align="center">
  <img src="docs/banner.png" alt="GKID Kernels Banner">
</p>

[![Build Status](https://github.com/ahmed-alnassif/GKID-Kernels/actions/workflows/build.yml/badge.svg)](https://github.com/ahmed-alnassif/GKID-Kernels/actions/workflows/build.yml)
[![Latest Release](https://img.shields.io/github/v/release/ahmed-alnassif/GKID-Kernels?label=Latest%20Release&color=00aa00)](https://github.com/ahmed-alnassif/GKID-Kernels/releases)
[![Downloads](https://img.shields.io/github/downloads/ahmed-alnassif/GKID-Kernels/total?label=Downloads&color=00aa00)](https://github.com/ahmed-alnassif/GKID-Kernels/releases)
[![Group](https://img.shields.io/badge/Telegram-Group-blue.svg?logo=telegram)](https://t.me/ahmed_alnassif_tg)
[![GitHub License](https://img.shields.io/github/license/ahmed-alnassif/GKID-Kernels?logo=gnu)](/LICENSE)
[![SuSFS](https://img.shields.io/badge/SuSFS-4CAF50?&logo=gitlab&logoColor=white)](https://gitlab.com/simonpunk/susfs4ksu)
[![KernelSU](https://img.shields.io/badge/KernelSU-000000?&logo=github&logoColor=white)](https://github.com/tiann/KernelSU)
[![ReSukiSU](https://img.shields.io/badge/ReSukiSU-E91E63?&logo=github&logoColor=white)](https://github.com/ReSukiSU/ReSukiSU)
[![Managers](https://img.shields.io/badge/Managers-multiple-success)](https://github.com/ahmed-alnassif/GKID-Kernels/releases)

**⚡ Blazing fast GKI kernel for Android** with KernelSU, SuSFS, NetHunter, NTSync, performance optimizations, battery improvements, and advanced security features.

---

> [!Important]
> - This is a **GKI** kernel, not a custom kernel. It works on **ANY** device that ships with a matching GKI Linux version.
> - Supported GKI versions: **5.10, 5.15, 6.1, 6.6, 6.12** (see [Supported GKI Kernel Versions](#-supported-gki-kernel-versions) below).

---

## ❤️ Support This Project

**[Donations](https://github.com/ahmed-alnassif#-support-my-work)**

Your donations keep this project alive! I spend countless hours maintaining kernel builds for 5 different versions, fixing bugs, adding features, and supporting users. **Every donation matters!** 🙏

---

## ✨ ReSuSFS 

**[ReSuSFS](https://github.com/ahmed-alnassif/ReSuSFS)** – Root hiding made simple, powerful when you need it. A [KernelSU](https://kernelsu.org) module and WebUI that turns SuSFS into clean config files and toggle switches for everyday use, with **strong hiding applied out of the box** via built-in spoofing and hiding scripts for one-tap protection, plus a script manager for power users who want more, all without leaving the WebUI.

---

## ⚡ Quick Start

1. **Check** your kernel version in Settings → About Phone
2. **Download** matching variant from [Releases](https://github.com/ahmed-alnassif/GKID-Kernels/releases)
3. **Flash** using KernelSU app or custom recovery
4. **Manage** SuSFS with [ReSuSFS](https://github.com/ahmed-alnassif/ReSuSFS)

---

## 📱 Supported GKI Kernel Versions

| Linux | Android |
|-------|---------|
| 5.10  | 12      |
| 5.15  | 13      |
| 6.1   | 14      |
| 6.6   | 15      |
| 6.12  | 16      |

---

## 🔧 Build Variants

| Variant | Root | SuSFS | LTO | Compat |
|---------|------|-------|-----|--------|
| Vanilla | ❌ | ❌ | Full | ❌ |
| Vanilla+NoLTO | ❌ | ❌ | None | ❌ |
| KernelSU | ✅ | ❌ | Full | ❌ |
| KernelSU+SuSFS | ✅ | ✅ | Full | ❌ |
| KSU+SuSFS+MM | ✅ | ✅ | Full | ❌ |
| ReSukiSU+SuSFS | ✅ | ✅ | Full | ❌ |
| Compat+KSU+SuSFS | ✅ | ✅ | Full | ✅ |

**Optional features** (enable on any variant):
- 🐳 DroidSpaces - Linux userspace support
- 🐉 NetHunter - Wireless penetration testing
- 🥷 NoMount - NoMount integration

---

## Performance

| Feature | Description |
|---------|-------------|
| **300Hz Timer** | Reduced input latency for snappier UI response |
| **MGLRU** | Multi-generational LRU for smoother multitasking |
| **zRAM** | LZ4 compression with writeback for memory efficiency |
| **CPU Governors** | schedutil + ondemand for smart power scaling |
| **I/O Scheduler** | mq-deadline optimized for UFS 4.0 storage |
| **F2FS Tuning** | 50ms GC sleep for buttery smooth I/O |
| **Memory Optimizations** | 50% faster memcpy/memset/memcmp operations |
| **ext4 Tuning** | Extended commit age reducing unnecessary writes |
| **NTSync Driver** | Faster Windows games/apps on Winlator/GameHub |

**What this means for you:**
- Apps launch faster
- UI feels more responsive
- Gaming has less stutter
- Multitasking is smoother
- Better framerates in games

---

## 🔋 Battery Life

| Feature | Description |
|---------|-------------|
| **Wakelock Cap** | 500ms cap prevents excessive battery drain |
| **Freeze Timeout** | 20s → 1s for faster deadlock detection |
| **F2FS Optimization** | Reduced GC overhead saves CPU cycles |
| **Alarm Wakeups** | Minimized to reduce standby battery drain |
| **ext4 Commit Age** | 30s commit age reduces write operations |
| **Power Management** | Improved suspend/resume for better idle drain |

**What this means for you:**
- Better standby time
- Less battery drain during use
- Overnight battery lasts longer
- Gaming doesn't kill battery as fast
- All-day battery life

---

## 🌐 Networking

| Feature | Description |
|---------|-------------|
| **TCP BBRv3** | Default congestion control for maximum speed |
| **Westwood+** | Alternative congestion control for WiFi |
| **FQ CoDel** | Fair queuing with controlled delay |
| **IP Set** | Efficient IP/network address management |
| **IPv4/IPv6 NAT** | Full NAT support for tethering |
| **IPsec/ESP** | VPN and secure tunneling support |
| **Netfilter** | Advanced firewall and packet filtering |

**What this means for you:**
- Faster WiFi and mobile data
- Better VPN performance
- Improved tethering speeds
- Lower gaming latency
- Smoother streaming

---

## 🛡️ Security

| Feature | Description |
|---------|-------------|
| **SuSFS** | Advanced filesystem and process hiding |
| **Baseband Guard** | Blocks unauthorized partition writes |
| **Kernel LSM** | SELinux + Baseband Guard integration |
| **Symbol Hiding** | Kernel symbol protection from detection |
| **uname Spoofing** | System information hiding |
| **Open Redirect** | Protected file operations |
| **SUS MAP/PATH/MOUNT** | Complete filesystem hiding |

**What this means for you:**
- Stronger root hiding
- Better banking app compatibility
- Improved security against detection
- Safe from unauthorized system modifications

---

## 🔑 Root Management

| Feature | Description |
|---------|-------------|
| **KernelSU** | Stable kernel-based root with excellent hiding |
| **ReSukiSU** | ReSukiSU kernel integration |
| **Multiple Managers** | Run multiple KernelSU managers simultaneously |
| **Vanilla** | No root for banking and corporate apps |

**What this means for you:**
- Reliable root access
- Apps don't detect root
- Pass SafetyNet/Play Integrity
- Choose your root implementation

---

## 🎮 NTSync

Linux NTSYNC interface for Windows gaming:
- Winlator
- GameHub
- ExaGear
- Other Windows emulation

**What this means for you:**
- Better Windows game performance
- Lower latency in emulators
- GKI compatibility patches included

---

## 🐳 DroidSpaces

Complete Linux userspace support:
- System V IPC and POSIX message queues
- IPC and PID namespaces
- devtmpfs with xattrs
- POSIX ACLs
- Netfilter and IP Set
- UFW and Fail2ban requirements

**What this means for you:**
- Run Linux apps on Android
- Better container support
- Chroot and proot work better

---

## 🐉 NetHunter

Wireless penetration testing features:
- cfg80211, mac80211, RFKILL
- Realtek rtw88, R8188EU drivers
- Atheros, MediaTek, Ralink, Zydas
- Bluetooth HCI and USB networking
- Monitor mode and packet injection

**What this means for you:**
- Kali NetHunter works perfectly
- External WiFi adapters supported
- Wireless auditing capabilities
- Monitor mode for packet capture

---

## 📦 WirelessKSU

Separate KernelSU module containing wireless drivers and firmware when built as modules. Flash alongside the main kernel for full NetHunter support.

---

## 🔥 LTO Options

| Option | Description | Best For |
|--------|-------------|----------|
| **FullLTO** | Maximum performance, slower build | Gaming, performance |
| **ThinLTO** | Faster build, good performance | Balanced |
| **NoLTO** | Build compatibility | Problem devices |

---

## 🔄 Compatibility

**Use Compat if:**
- You experience boot issues
- Standard variants don't boot

---

## 📥 Downloads

**All releases:** [GitHub Releases](https://github.com/ahmed-alnassif/GKID-Kernels/releases)

**Each release includes:**
- 📦 AnyKernel3 flashable packages
- 📦 WirelessKSU modules (when applicable)
- 🔐 SHA256 and MD5 checksums
- 📝 Build information and changelogs

---

## 📡 TCP Congestion Control

Switch congestion control algorithms (temporary, resets on reboot):

```bash
# Westwood+ - better for WiFi and mobile data
su -c "sysctl -w net.ipv4.tcp_congestion_control=westwood"

# BBRv3 - default, best for speed
su -c "sysctl -w net.ipv4.tcp_congestion_control=bbr"
```

**Make permanent:** Create a script in `/data/adb/service.d/` with the sysctl command or use ReSuSFS.

---

## Other Ways to Help

- **Star the Repository** ⭐ - Helps others discover this project
- **Share** 📢 - Spread the word in your community or forums
- **Report Issues** 🐛 - Found a bug? Open an issue with detailed logs
- **Contribute** 🔧 - Pull requests, suggestions, and feedback are always welcome

---

## 💬 Community

- **Telegram:** [@ahmed_alnassif_tg](https://t.me/ahmed_alnassif_tg)
- **Discussions:** [GitHub Discussions](https://github.com/ahmed-alnassif/GKID-Kernels/discussions)
- **Issues:** [GitHub Issues](https://github.com/ahmed-alnassif/GKID-Kernels/issues)

---

## 📄 License

See [LICENSE](LICENSE).