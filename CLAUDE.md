# Cogan — petunjuk untuk Claude

Baca **`docs/WORK-AGREEMENT.md`** sebelum mengerjakan apa pun. Isinya aturan kerja (bagian A), peta pekerjaan berprioritas (C) dan checkpoint (E).

- **Mulai sesi / owner mengetik `lanjutkan`:** baca entri terbaru di bagian *E. Checkpoint*, lalu kerjakan langkah **Berikutnya** di sana atau item teratas yang belum selesai di bagian C.
- **Owner mengetik `checkpoint`:** ikuti aturan A15: tulis entri checkpoint (Selesai / Sedang berjalan / Berikutnya / Menunggu owner), perbarui status di bagian C, commit + push ke branch kerja, laporkan hash commit.
- Branch utama `dev`; perubahan masuk lewat PR. Keputusan merge/squash dan perampingan issue/PR ada di Claude (A17). Workflow build kernel, rilis dan flash hanya owner (A10, A16); compile lokal boleh.
- Ruang lingkup kernel 6.1 saja (A11). Kernel khusus Xiaomi 14T Pro (rothko) dibangun di repo `cogan17/Xiomi-14t-pro` (workflow rothko di sana memakai `build.sh` Cogan pada commit yang dipin, dengan `TARGET_DEVICE=rothko`); Cogan adalah kernel GKI umum + mesin build.
- Bahasa dokumen dan laporan: Indonesia; README dan rilis juga berbahasa Inggris.
