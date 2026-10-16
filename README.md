<div align="center">

# Cogan Kernel

**Kernel GKI 6.1 untuk Android dengan KernelSU, KernelSU Next, BakaSU dan SUSFS**

**🇮🇩 Bahasa Indonesia** · [🇬🇧 English](README.en.md)

[![Lisensi: GPL-3.0](https://img.shields.io/badge/lisensi-GPL--3.0-blue.svg)](LICENSE)
[![GKI android14-6.1](https://img.shields.io/badge/GKI-android14--6.1-3DDC84.svg?logo=android&logoColor=white)](#perangkat-yang-didukung)
[![Rilis](https://img.shields.io/github/v/release/cogan17/Cogan?include_prereleases&label=rilis)](https://github.com/cogan17/Cogan/releases)

</div>

> [!CAUTION]
> Cogan tidak bertanggung jawab atas perangkat yang rusak (*brick*) atau data yang hilang. Dengan mem-flash, Anda menanggung semua risikonya. Cadangkan data dan siapkan `boot.img` stock **sebelum** flash. Lihat **[Panduan Bootloop](docs/bootloop.md)**.

---

## Tentang

Kernel generik yang dibangun dari sumber GKI 6.1 ([GKI-Duchamp-6.1](https://github.com/ahmed-alnassif/GKI-Duchamp-6.1)) dengan root berbasis kernel dan SUSFS untuk menyembunyikan root. Dibuat agar cocok dengan banyak perangkat GKI `android14-6.1`, tetapi tidak dijamin berjalan di semua perangkat.

---

## Fitur

- **KernelSU / KernelSU Next / BakaSU**: root berbasis kernel
- **SUSFS**: menyembunyikan root (sus path, sus mount, sus kstat, sus map, spoof uname dan cmdline, open redirect, sembunyikan simbol)
- **NoMount**: metamodul mount, selalu ikut
- **Baseband Guard (BBG)**: melindungi partisi penting dari penulisan tanpa izin (bisa dimatikan)
- **Networking**: TCP BBRv3 (default), Westwood+, FQ, IP Set, NAT IPv6 (bisa dimatikan)
- **Performa**: timer 300 Hz, MGLRU, zRAM LZ4 + writeback, mq-deadline, kompresi F2FS, NTSync
- **TMPFS**: xattr dan POSIX ACL
- **Toolchain**: Neutron Clang (versi dikunci) dengan pilihan Full LTO, Thin LTO, atau tanpa LTO
- **Komponen terkunci**: kernel, root manager, SUSFS, NoMount, BBG, AnyKernel3 dan toolchain dipin ke commit tertentu, dan hanya diperbarui lewat **Cogan Manual Update**. Root manager dan NoMount mengikuti **tag rilis resmi**, jadi APK manager dan modul NoMount selalu versi yang sama dengan kernel

---

## Perangkat yang didukung

- Perangkat dengan kernel stock **GKI `6.1.x-android14`**. Cek di *Setelan → Tentang ponsel → Spesifikasi lengkap → Versi kernel*.
- Sublevel tersedia **6.1.160 ke atas**; `lts` = sublevel terbaru. Pilih sublevel yang **sama atau lebih baru** dari kernel stock Anda.
- Bootloader harus sudah terbuka.

---

## Varian

| Pilihan di form | Nama varian (ZIP) | Root | SUSFS | Catatan |
|---|---|---|---|---|
| KernelSU | `KernelSU` | KernelSU | ❌ | |
| KernelSU + SUSFS | `KernelSU+SuSFS` | KernelSU | ✅ | |
| KernelSU Next | `KernelSU-Next` | KernelSU Next | ❌ | |
| KernelSU Next + SUSFS (uji) | `KernelSU-Next+SuSFS+Test` | KernelSU Next (fork pershoot) | ✅ | **Khusus uji**: hanya 6.1.177 (`lts`), Full LTO, BBG aktif |
| BakaSU + SUSFS | `BakaSU+SuSFS` | BakaSU | ✅ | |
| Vanilla | `Vanilla` | ❌ | ❌ | Tanpa root |
| All variants (advanced) | Semua varian standar + `Vanilla+NoLTO` + `Compat+…` | | | `Compat` tanpa LTO, untuk perangkat yang tidak mau boot dengan varian standar |

---

## Unduh & pasang

1. Pastikan kernel stock Anda `6.1.x-android14` dan bootloader sudah terbuka.
2. **Siapkan `boot.img` stock** yang sama persis dengan versi ROM Anda ([caranya](docs/bootloop.md#1-siapkan-bootimg-stock-sebelum-flash)).
3. Unduh ZIP dari **[Releases](https://github.com/cogan17/Cogan/releases)**, lalu cocokkan SHA256-nya dengan `checksums.txt`.
4. Flash ZIP AnyKernel3 dengan aplikasi flasher kernel di perangkat yang sudah root, misalnya [Kernel Flasher](https://github.com/capntrips/KernelFlasher) atau [Horizon Kernel Flasher](https://github.com/libxzr/HorizonKernelFlasher), atau lewat custom recovery. ZIP ini **tidak** bisa di-flash lewat `fastboot`.
5. Pasang APK manager yang versinya sama dengan kernel. APK ini ikut di artifact build; bisa juga diunduh dari rilis resmi dengan tag yang sama: [KernelSU](https://github.com/tiann/KernelSU/releases), [KernelSU Next](https://github.com/KernelSU-Next/KernelSU-Next/releases) atau [BakaSU](https://github.com/Baka-SU/BakaSU/releases). Modul NoMount (ZIP) dipasang lewat menu Modul di manager.
6. Reboot. Kalau macet di logo atau terus restart, buka **[Panduan Bootloop](docs/bootloop.md)**.

---

## Bootloop?

Jangan panik dan **jangan factory reset**. Biasanya cukup mem-flash kembali `boot.img` stock lewat fastboot. Langkah lengkap, termasuk bagian khusus **Xiaomi 14T Pro (rothko)**, ada di **[Panduan Bootloop](docs/bootloop.md)**.

---

## Build sendiri

Buka **Actions → Cogan Kernel Builder → Run workflow** di repositori Anda.

| Isian | Keterangan |
|---|---|
| Root Manager | Varian yang dibangun (lihat tabel Varian) |
| Build Mode | `Standard Build` |
| LTO Package | Full LTO (default), Thin LTO, atau tanpa LTO; NoMount selalu ikut |
| Kernel Version | Dikunci `6.1` |
| Build Revision | Opsional, format `r` + angka (mis. `r9`), ditambahkan ke nama rilis |
| Kernel Sublevel | `lts` = terbaru, atau angka saja (mis. `177`, bukan `6.1.177`); tersedia 6.1.160 ke atas |
| Build Time | `N` = waktu build asli, atau waktu tetap seperti `Thu Jan 1 00:00:00 UTC 2026` |
| Networking | BBRv3 dan paket jaringan tambahan (default aktif) |
| BBG | Baseband Guard (default aktif) |

**Hasil build:** saat run hijau, artifact bernomor bisa langsung diunduh (tidak perlu diekstrak):

| File | Isi | Cara pakai |
|---|---|---|
| `1-KERNEL_Cogan-6.1.x_<varian>_<rilis>.zip` | Kernel (ZIP AnyKernel3) | Flash dengan Kernel Flasher |
| `2-MANAGER_<root manager>_<versi>.apk` | Root manager resmi, tag rilis sama dengan kernel | Install APK |
| `3-MANAGER-SPOOFED_<root manager>_<versi>.apk` | Manager yang sama, nama paket acak (lebih sulit dideteksi); hanya jika rilis resminya menyediakan, saat ini KernelSU Next | Install **salah satu**: 2 atau 3 |
| `4-NOMOUNT-MODULE_<versi>.zip` | Modul NoMount resmi, versi sama dengan NoMount di kernel | Pasang di manager → Modul |

Artifact `build-…` dan `build-env-…` adalah file internal; abaikan saja. Ringkasan run berisi tabel yang sama beserta SHA256. Semua versi ini dikunci bersama oleh **Cogan Manual Update**. Kalau upstream sudah merilis versi yang lebih baru, ringkasan run menampilkan **🔔 Pengingat**: jalankan Cogan Manual Update (`update` → `root-managers` atau `nomount`), lalu build ulang supaya kernel, root manager dan NoMount naik bersama.

**Memperbarui komponen:** buka **Actions → Cogan Manual Update**.
- `check` hanya menampilkan laporan versi.
- `update` langsung menerapkan versi baru ke `dev`.

Run workflow build hanya meng-compile dan tidak pernah memperbarui komponen sendiri.

---

## Terima kasih

- **GKID Kernels dan GKI-Duchamp-6.1**: [Ahmed Al-Nassif](https://github.com/ahmed-alnassif) (proyek dasar dan sumber kernel)
- **KernelSU**: [tiann](https://github.com/tiann/KernelSU)
- **KernelSU Next**: [KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next)
- **KernelSU Next fork SUSFS**: [pershoot](https://github.com/pershoot/KernelSU-Next)
- **BakaSU**: [Baka-SU](https://github.com/Baka-SU/BakaSU)
- **SUSFS**: [simonpunk](https://gitlab.com/simonpunk/susfs4ksu)
- **NoMount**: [maxsteeel](https://github.com/maxsteeel/nomount)
- **Baseband Guard (BBG)**: [vc-teahouse](https://github.com/vc-teahouse/Baseband-guard)
- **AnyKernel3**: [osm0sis](https://github.com/osm0sis/AnyKernel3) (lewat [AK3-GKID](https://github.com/ahmed-alnassif/AK3-GKID))
- **Neutron Clang**: [Neutron-Toolchains](https://github.com/Neutron-Toolchains/clang-build-catalogue)
- Tampilan README terinspirasi [Wild Kernels](https://github.com/WildKernels/GKI_KernelSU_SUSFS)

Menemukan bug? Buka [Issue](https://github.com/cogan17/Cogan/issues) dan lampirkan log. Caranya ada di [Panduan Bootloop](docs/bootloop.md#4-setelah-berhasil-boot-ambil-log).

---

## Lisensi

[GPL-3.0](LICENSE)
