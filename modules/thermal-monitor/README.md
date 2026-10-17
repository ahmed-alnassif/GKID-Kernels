# Cogan Thermal Monitor

[English](README.en.md)

Modul KernelSU / KernelSU Next / BakaSU (juga Magisk, tanpa WebUI) yang mencatat **semua suhu** HP beserta **penyebabnya**, lalu membuat ringkasan. Modul hanya membaca sensor; tidak mengubah setelan HP dan tidak mengirim data ke mana pun.

## Yang dicatat

Tiap 20 detik (bisa diubah):

- semua sensor `thermal_zone` (prosesor, GPU, baterai, badan HP, modem, charger, AI/APU, PMIC, Wi-Fi), dikelompokkan otomatis;
- aplikasi yang sedang dibuka, layar nyala/mati;
- pemakaian CPU, proses kernel, 5 proses tersibuk (termasuk yang di latar belakang), beban GPU;
- status cas dan arusnya, kecepatan Wi-Fi/data seluler, frekuensi CPU;
- versi kernel yang dipakai (untuk membandingkan, misalnya Cogan dengan kernel bawaan).

Riwayat disimpan di `/data/adb/cogan_thermal`, maksimal 7 hari (bisa diubah).

## Penyebab panas

Tiap momen panas (bawaan ≥ 42 °C) diberi satu penyebab, urut dari yang paling kuat:

1. **Cas cepat**: mengecas ≥ 1500 mA.
2. **Grafis berat: _aplikasi_**: GPU ≥ 60 % (game seperti Mobile Legends).
3. **Latar belakang: _proses_**: proses lain (bukan aplikasi yang dibuka) memakai ≥ 10 % CPU.
4. **Proses kernel**: thread kernel memakai ≥ 10 % CPU.
5. **Data seluler berat (modem)**: ≥ 1,5 MB/s.
6. **Layar mati** (proses latar) atau **mengecas** saat layar mati.
7. **Aplikasi berat: _aplikasi_**: CPU ≥ 25 % (Instagram, kamera, dll.).
8. **Mengecas**, atau **Pemakaian ringan** (sisa panas / suhu sekitar).

Persen CPU dihitung dari kapasitas semua inti (8 inti: satu inti penuh ≈ 12,5 %).

## WebUI

Buka modul di manager → ikon WebUI:

- **Sekarang**: suhu terpanas, tiap bagian HP, dan semua sensor (diperbarui tiap 5 detik).
- **Ringkasan**: 15 menit sampai 7 hari, berisi grafik, suhu tertinggi, penyebab panas, per aplikasi, per kernel. Tombol **📋 Salin** menyalin ringkasan sebagai teks.
- **💾 Simpan log**: pilih rentang (15 menit sampai 7 hari, atau isi menit sendiri). File `.txt` (ringkasan + detail tiap sampel) dan `.csv` masuk ke `Download/CoganThermal`.
- **⚙️ Setelan**: jeda cek, batas panas, lama riwayat, notifikasi panas (mati secara bawaan; batas 45 °C), tombol mulai/hentikan dan hapus riwayat.

Tombol **Action** di manager menampilkan ringkasan 1 jam terakhir.

## Pasang / hapus

- Pasang ZIP lewat menu Modul, lalu reboot.
- Hapus modul: riwayat di `/data/adb/cogan_thermal` ikut terhapus; log di `Download/CoganThermal` tetap ada.

## Untuk pengembang

- Buat ZIP: `python3 scripts/package_module.py modules/thermal-monitor out/`
- Uji offline (sysfs/proc palsu): `python3 -m unittest tests/test_thermal_monitor.py`
- Skrip: `sampler.sh` (pencatat), `report.sh` (laporan untuk WebUI/Action), `report.awk` + `thermal.awk` + `cpu.awk` (awk POSIX, cocok dengan awk Android).
