# Panduan Bootloop

**🇮🇩 Bahasa Indonesia** · [🇬🇧 English](bootloop.en.md) · [← README](../README.md)

> [!IMPORTANT]
> Lakukan **bagian 1 sebelum mem-flash kernel apa pun**. Tanpa `boot.img` stock, pemulihan jauh lebih sulit.

---

## Tanda bootloop

- HP macet di logo, terus restart, atau masuk fastboot sendiri.
- Boot pertama setelah flash kernel biasanya tidak lebih lama dari boot biasa. Jika lebih dari ±5 menit belum sampai layar kunci, anggap bootloop.

---

## Kernel atau modul?

Cara memulihkan dan log yang perlu diambil berbeda, jadi kenali dulu penyebabnya.

| Gejala | Penyebab paling mungkin | Langkah |
|---|---|---|
| Restart atau macet di **logo pertama** (logo merek / tulisan *unlocked*); animasi boot tidak pernah muncul | **Kernel** | [Bagian 2](#2-pulihkan-dari-bootloop): flash `boot.img` stock |
| Bootloop tepat setelah **flash kernel baru**, tanpa memasang modul | **Kernel** | [Bagian 2](#2-pulihkan-dari-bootloop) |
| **Animasi boot** muncul, lalu berulang atau macet lama | Biasanya **modul** | Coba safe mode di bawah dulu |
| Bootloop tepat setelah **memasang atau memperbarui modul** | **Modul** | Safe mode di bawah |

**Tes safe mode** (KernelSU; KernelSU Next dan BakaSU adalah turunannya):

1. Paksa restart: tahan tombol **Power** sampai HP mati dan menyala lagi.
2. Begitu **logo pertama** muncul, tekan **Volume Bawah lebih dari 3 kali**: tekan-lepas, tekan-lepas, tekan-lepas, **bukan** ditahan. Harus cepat, karena kesempatannya habis sebelum animasi boot muncul. Kalau terlewat, ulangi dari langkah 1.
3. Dalam safe mode **semua modul dinonaktifkan**:
   - **HP menyala → penyebabnya modul.** Buka manager → **Modul**, hapus (*uninstall*) modul yang baru dipasang atau diperbarui, lalu restart. Ambil lognya dulu kalau mau melapor ([bagian 4](#4-setelah-berhasil-boot-ambil-log)).
   - **Tetap bootloop → kemungkinan kernel.** Lanjut ke [bagian 2](#2-pulihkan-dari-bootloop).
4. Di HyperOS/MIUI, safe mode sistem juga bisa dibuka dari recovery bawaan (**Volume Atas + Power**, jika menunya ada); KernelSU ikut menonaktifkan modul.

Safe mode tidak menghentikan skrip `init.rc` milik modul. Jika modul seperti itu penyebabnya, gunakan cara manual di [panduan resmi KernelSU](https://kernelsu.org/guide/rescue-from-bootloop.html) atau flash `boot.img` stock ([bagian 2](#2-pulihkan-dari-bootloop)).

---

## 1. Siapkan `boot.img` stock (sebelum flash)

AnyKernel3 menulis kernel ke partisi **`boot`** pada slot aktif. Untuk memulihkannya Anda butuh `boot.img` dari versi ROM yang **sama persis**.

**Pilihan A: salin dari HP (sudah root)**

- Aplikasi [Kernel Flasher](https://github.com/fatalcoder524/KernelFlasher): pilih slot aktif, lalu *Backup*.
- Atau lewat ADB:

```sh
adb shell
su
dd if=/dev/block/by-name/boot$(getprop ro.boot.slot_suffix) of=/sdcard/boot-stock.img
exit
exit
adb pull /sdcard/boot-stock.img
```

**Pilihan B: ambil dari ROM resmi**

- Unduh ROM resmi dengan versi yang sama persis (lihat *Setelan → Tentang ponsel*).
- ROM fastboot: ambil `images/boot.img`.
- ROM recovery/OTA (berisi `payload.bin`): ekstrak `boot.img` dengan [payload-dumper-go](https://github.com/ssut/payload-dumper-go).

Simpan `boot.img` di PC. Pasang juga [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) (berisi `adb` dan `fastboot`), dan driver USB jika memakai Windows.

Jika sebelumnya Anda mem-patch `init_boot` (Magisk atau KernelSU mode LKM), simpan juga `init_boot.img` stock.

---

## 2. Pulihkan dari bootloop

1. Masuk mode **fastboot**. Kombinasi tombolnya tergantung HP; untuk Xiaomi lihat bagian 3.
2. Hubungkan ke PC, lalu cek dengan `fastboot devices`.
3. Flash kembali `boot.img` stock ke slot aktif:

```sh
fastboot getvar current-slot
fastboot flash boot boot-stock.img
fastboot reboot
```

`fastboot flash boot` otomatis menulis ke slot aktif. Data Anda **tidak** terhapus.

4. Jika Anda juga mengubah `init_boot`, jalankan juga `fastboot flash init_boot init_boot-stock.img`.

Bootloop karena kernel **tidak** perlu `fastboot -w`, `fastboot erase` atau factory reset.

---

## 3. Khusus Xiaomi 14T Pro (rothko)

| | |
|---|---|
| Codename | `rothko` |
| SoC | MediaTek Dimensity 9300+ (MT6989) |
| Partisi | A/B (slot `_a` / `_b`) |
| Kernel stock | GKI `android14-6.1` (contoh `6.1.138-android14-11`) |
| ROM | HyperOS (contoh `OS3.0.301.0.WNNIDXM`) |

**Flash `boot` atau `init_boot`?** Flash **`boot`** saja. HP ini dirilis dengan Android 14, jadi kernel ada di partisi `boot`; `init_boot` hanya berisi ramdisk, dan ZIP Cogan tidak pernah mengubahnya. `init_boot.img` stock hanya perlu di-flash juga jika Anda pernah mem-patch `init_boot` sendiri (Magisk atau KernelSU mode LKM).

**Masuk fastboot:** tahan **Volume Bawah + Power** sampai muncul tulisan **FASTBOOT**. Saat bootloop, cukup tahan kedua tombol sampai layar fastboot muncul.

**Langkah:**

1. Pastikan `boot.img` berasal dari versi HyperOS yang **sama persis** dengan yang terpasang.
2. Jalankan perintah di bagian 2.
3. HP menyala dengan kernel stock, dan data tetap aman.

**Jangan pernah:**

- Menjalankan `flash_all_lock` dari ROM fastboot. Skrip ini mengunci bootloader; dengan partisi yang sudah diubah, HP bisa mati total (*hard brick*).
- Mem-flash ROM yang **lebih lama** dari versi terpasang. Xiaomi memakai anti-rollback, dan downgrade bisa membuat HP mati total.
- Memakai SP Flash Tool atau mode BROM MediaTek. Biasanya butuh akun resmi Xiaomi, dan bisa menghapus kalibrasi modem/IMEI.
- Mem-flash `boot.img` ke partisi lain (`init_boot`, `vendor_boot`, dan seterusnya).

Recovery bawaan Xiaomi (**Volume Atas + Power**) tidak bisa mem-flash `boot.img`, jadi gunakan fastboot.

**Masih bootloop setelah flash `boot.img` stock?**

1. Flash ROM fastboot resmi dengan versi yang sama memakai `flash_all_except_storage` (data tetap ada).
2. Jika tetap gagal, bawa ke service center resmi Xiaomi.

---

## 4. Setelah berhasil boot: ambil log

Ambil log **segera** setelah HP kembali menyala, sebelum restart lagi. Semua perintah lewat CMD (Platform Tools) juga dirangkum di [README → Pakai CMD](../README.md#pakai-cmd-platform-tools).

### Bootloop karena kernel

Pesan *panic* dari boot yang gagal tersimpan sementara di memori (**pstore**). Isinya **tertimpa setelah restart berikutnya** dan hilang jika HP mati total.

1. Setelah HP menyala dengan `boot.img` stock (tanpa root), ambil bugreport lewat *Opsi pengembang → Laporan bug → Laporan lengkap*, atau jalankan `adb bugreport` dari PC. Bugreport ikut menyimpan isi pstore.
2. Mau melihat sendiri? Buka file `.txt` utama di dalam ZIP bugreport, lalu cari bagian `LAST KMSG` atau kata kunci `Kernel panic`, `Unable to handle kernel` dan `Call trace`.
3. Jika HP sudah root lagi, pstore juga bisa disalin langsung:

```sh
adb shell "su -c 'cat /sys/fs/pstore/console-ramoops*'" > ramoops.txt
```

### Bootloop karena modul

1. Masuk **safe mode** ([caranya](#kernel-atau-modul)). Root tetap jalan, hanya modul yang mati.
2. Di manager buka **Pengaturan → Kirim log** atau **Simpan log** (nama menu bisa sedikit berbeda di KernelSU Next dan BakaSU). ZIP-nya berisi `dmesg`, `logcat`, pstore dan log KernelSU (`/data/adb/ksu/log`).
3. Kalau **USB debugging sudah aktif dan PC sudah pernah diizinkan**, log bisa direkam langsung saat animasi boot berputar:

```sh
adb logcat -b all > logcat-bootloop.txt
```

   Tekan `Ctrl+C` setelah ±1 menit. Cari `FATAL EXCEPTION`, `system_server` atau path `/data/adb/modules/<nama-modul>`.
4. Mencari modul penyebabnya: aktifkan modul **satu per satu** di manager dan restart setiap kali. Modul terakhir yang diaktifkan sebelum bootloop adalah penyebabnya.

### Lapor

Buka [Issue](https://github.com/cogan17/Cogan/issues) dan lampirkan:

- file bugreport (`.zip`) dan/atau ZIP log dari manager,
- nama ZIP kernel yang di-flash (varian dan nomor rilis atau run),
- daftar modul yang terpasang (jika penyebabnya modul),
- model HP dan versi ROM.

Bugreport seperti inilah yang dipakai untuk menemukan penyebab bootloop KernelSU Next + SUSFS saat masih tahap uji ([catatan](validation/ksun-susfs-6.1-bootloop-fix.json)).

---

## 5. Mencoba lagi dengan aman

- Pilih sublevel yang **sama atau lebih baru** dari kernel stock.
- Varian `Compat` (dibuat lewat **All variants (advanced)**) dibangun tanpa LTO untuk HP yang tidak mau boot dengan varian standar.
- Varian bertanda **(uji)** hanya untuk pengujian. Selalu siapkan `boot.img` stock sebelum mencobanya.
