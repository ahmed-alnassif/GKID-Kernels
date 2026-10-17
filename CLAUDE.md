# Cogan — petunjuk untuk Claude

Baca **`docs/WORK-AGREEMENT.md`** sebelum mengerjakan apa pun. Isinya aturan kerja (bagian A), peta pekerjaan berprioritas (C) dan checkpoint (E).

- **Mulai sesi / owner mengetik `lanjutkan`:** baca entri terbaru di bagian *E. Checkpoint*, lalu kerjakan langkah **Berikutnya** di sana atau item teratas yang belum selesai di bagian C.
- **Owner mengetik `checkpoint`:** ikuti aturan A15: tulis entri checkpoint (Selesai / Sedang berjalan / Berikutnya / Menunggu owner), perbarui status di bagian C, commit + push ke branch kerja, laporkan hash commit, **lalu berhenti total** sampai owner meminta lanjut (link atau laporan dari owner bukan izin lanjut).
- Branch utama `dev`; perubahan masuk lewat PR. Keputusan merge/squash dan perampingan issue/PR ada di Claude (A17). Workflow build kernel, rilis dan flash hanya owner (A10, A16), kecuali owner meminta Claude menjalankan workflow secara eksplisit; compile lokal boleh.
- **Cogan tidak boleh terganggu (A18, aturan terpenting owner).** Cogan adalah kernel GKI 6.1 umum + mesin build; jangan tambahkan kode khusus perangkat (rothko, `TARGET_DEVICE`, sumber kernel bawaan, gate KMI) ke Cogan. Kernel Xiaomi 14T Pro (rothko) dikembangkan di repo `cogan17/Xiomi-14t-pro` dengan salinan mesin sendiri (branch `rothko-engine`, D-021); repo itu tidak menulis apa pun ke Cogan. Perbaikan umum dibuat di Cogan dulu, lalu disalin manual (cherry-pick) ke Xiomi. Bila pekerjaan rothko butuh mengubah Cogan, tanya owner dulu.
- Ruang lingkup kernel 6.1 saja (A11).
- Bahasa dokumen dan laporan: Indonesia; README dan rilis juga berbahasa Inggris.
