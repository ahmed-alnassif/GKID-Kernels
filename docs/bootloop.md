# Panduan Bootloop

**🇮🇩 Bahasa Indonesia** · [🇬🇧 English](bootloop.en.md) · [← README](../README.md)

> [!IMPORTANT]
> Lakukan **bagian 1 sebelum mem-flash kernel apa pun**. Tanpa `boot.img` stock, pemulihan jauh lebih sulit.

---

## Tanda bootloop

- HP macet di logo, terus restart, atau masuk fastboot sendiri.
- Boot pertama setelah flash kernel biasanya tidak lebih lama dari boot biasa. Jika lebih dari ±5 menit belum sampai layar kunci, anggap bootloop.

---

## 1. Siapkan `boot.img` stock (sebelum flash)

AnyKernel3 menulis kernel ke partisi **`boot`** pada slot aktif. Untuk memulihkannya Anda butuh `boot.img` dari versi ROM yang **sama persis**.

**Pilihan A: salin dari HP (sudah root)**

- Aplikasi [Kernel Flasher](https://github.com/capntrips/KernelFlasher): pilih slot aktif, lalu *Backup*.
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

Log panic dari boot yang gagal tersimpan sementara di memori (pstore) dan **tertimpa setelah restart berikutnya**. Karena itu, segera setelah HP kembali menyala:

1. Ambil bugreport lewat *Opsi pengembang → Laporan bug → Laporan lengkap*, atau jalankan `adb bugreport` dari PC.
2. Buka [Issue](https://github.com/cogan17/Cogan/issues) dan lampirkan:
   - file bugreport (`.zip`),
   - nama ZIP kernel yang di-flash (varian dan nomor rilis atau run),
   - model HP dan versi ROM.

Bugreport seperti inilah yang dipakai untuk menemukan penyebab bootloop varian uji KernelSU Next + SUSFS ([catatan](validation/ksun-susfs-6.1-bootloop-fix.json)).

---

## 5. Mencoba lagi dengan aman

- Pilih sublevel yang **sama atau lebih baru** dari kernel stock.
- Varian `Compat` (dibuat lewat **All variants (advanced)**) dibangun tanpa LTO untuk HP yang tidak mau boot dengan varian standar.
- Varian bertanda **(uji)** hanya untuk pengujian. Selalu siapkan `boot.img` stock sebelum mencobanya.
