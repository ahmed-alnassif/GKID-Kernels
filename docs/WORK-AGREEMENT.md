# Kesepakatan Kerja & Peta Pekerjaan

Dokumen ini adalah sumber utama aturan kerja dan urutan prioritas. Owner cukup mengetik **`lanjutkan`**; pekerjaan diambil dari item teratas yang belum selesai di bagian *Peta Pekerjaan*.

## A. Aturan kerja

1. **Petakan dulu, kerjakan kemudian.** Semua pekerjaan tercatat di peta di bawah dengan prioritas (P0 tertinggi). Tidak ada pekerjaan di luar peta tanpa ditambahkan dulu.
2. **Tidak ada pekerjaan ganda.** Cek peta, checkpoint, dan run hijau sebelum mulai. Pengulangan cek/test **maksimal 2 kali** (idealnya 1 kali) per perubahan.
3. **Hemat sumber daya.** Gabungkan perubahan kecil dalam satu commit/push yang bermakna; hindari push beruntun yang hanya memicu CI berulang.
4. **CI selektif.**
   - Run yang sudah **hijau** dicatat sebagai bukti keberhasilan (ID run) dan tidak dijalankan ulang.
   - Run **merah**: baca log dulu, cari akar masalah, perbaiki, lalu jalankan **satu** run verifikasi. Tidak boleh "coba-coba" berulang.
   - Re-run hanya bila benar-benar perlu (mis. runner mati sebelum test berjalan).
5. **PR selektif.** Satu PR = satu topik, kecil, berbasis branch tujuan yang benar. Jangan membuka PR antar branch yang tidak punya riwayat bersama (penyebab "This pull is big, showing recent 250").
6. **Rapikan issue/PR/branch** secara berkala; yang tidak perlu ditutup dengan alasan. Tidak wajib segera, tapi tidak boleh menumpuk.
7. **Tidak ada yang terbengkalai.** Pekerjaan sulit boleh ditunda, tetapi tetap tercatat di peta dengan status dan alasan.
8. **Judul workflow harus sesuai isi pekerjaannya.** Ketidaksesuaian dicatat dan diperbaiki.
9. **Checkpoint secukupnya.** Hanya di akhir satu blok kerja yang berarti (bukan setiap langkah), ditulis di bagian *Checkpoint* dokumen ini.
10. **Kompilasi kernel hanya manual oleh owner** (2026-10-15): Claude tidak menjalankan compile kernel di mana pun — tidak di GitHub Actions, tidak di container sesi. Claude hanya menyiapkan source/config, memeriksa log/hasil yang diberikan owner, dan memperbaiki penyebab kegagalan. Release, flash, dan penghapusan production guard juga hanya keputusan owner.

## B. Temuan audit (2026-10-15)

| # | Temuan | Dampak |
|---|--------|--------|
| T1 | `master` dan `dev` **tidak punya riwayat bersama** (root commit berbeda; master 351 commit, dev 50). | PR `dev → master` akan menampilkan ratusan commit / ±18k baris → "This pull is big". |
| T2 | Fix SUSFS di `master` (#25 fail-fast patch, #26 cek `.config` ketat) **belum ada di `dev`**. Di `dev`, `error()` tidak menghentikan build, jadi kegagalan SUSFS bisa lolos diam-diam. | Risiko build "hijau" tanpa SUSFS aktif. |
| T3 | 22 branch lama (PR #1–#24 sudah ditutup) masih ada, semuanya berbasis riwayat `master`, bukan `dev`. | Berantakan, membingungkan saat memilih basis PR. |
| T4 | PR #27 (draft) berbasis `master`, 76 commit, menyentuh `build.yml`/`build.sh` yang di `dev` sudah jauh berbeda. | Konflik besar; perlu dipilah, bukan di-merge apa adanya. |
| T5 | Workflow `Validate` jalan di **setiap push** (sudah 405 run), banyak hanya untuk commit dokumen. | Boros CI. |
| T6 | Run `Cogan Kernel Builder` #7 (38720157010) merah: input `KernelSU Next + SUSFS` sengaja diblok guard (`build.yml:140`). | **Bukan bug** — guard bekerja sesuai desain. Tidak perlu re-run. |
| T7 | Nama workflow `Cogan Manual Update` berada di file `cogan-smart-auto-update.yml`; `Upload artifacts to telegram` dinonaktifkan manual tapi masih ada. | Judul vs isi tidak selaras (aturan A8). |

## C. Peta pekerjaan (urut prioritas)

| ID | Prio | Pekerjaan | Status |
|----|------|-----------|--------|
| W1 | P0 | Port fix SUSFS #25 + #26 dari `master` ke `dev` (fail-fast patch & cek `.config` yang benar-benar menghentikan build). Uji lokal sekali. | **Selesai** 2026-10-15 — hunk identik dengan `7e13e87`/`eab1188`; `validate_shell.py` OK, 60 unit test OK |
| W2 | P0 | Tetapkan **satu branch utama**. | **Diputuskan** 2026-10-15 — `dev` branch utama (sudah default di GitHub); `master` dibekukan, tidak diubah. Semua PR ke `dev` |
| W3 | P1 | Integrasi SUSFS 6.1: `git apply --check` patch kandidat BBG spinlock pada source asli, terapkan sekali, review jalur locking (lanjutan handoff `docs/validation/ksun-susfs-6.1-work-handoff.md`). | **Selesai** 2026-10-15 — check PASS, diterapkan sekali, locking aman. Integrasi ke replay = keputusan owner |
| W4 | P1 | Lanjutan SUSFS 6.1: `pahole`, generate `.config` di direktori baru, jalankan resolved-config gate. Baru setelah lulus → izin owner untuk compile terisolasi. | **Selesai** 2026-10-15 — `.config` `41492e89…` lulus gate, `make prepare` lulus |
| W4b | P1 | Satu compile penuh terisolasi (vmlinux/Image) dengan identitas persis dari `ksun-susfs-6.1-resolved-config.json`; putuskan dulu patch BBG `003`. | **Manual oleh owner** — Claude tidak menjalankan compile; setelah owner compile, Claude menganalisis log/hasil |
| W5 | P2 | Pilah PR #27: ambil hanya bagian yang masih relevan (sublevel opsional, DroidSpaces off) ke PR kecil baru berbasis `dev`; tutup #27 dengan alasan. | **Selesai** 2026-10-15 — isi #27 sudah tergantikan `dev` (sublevel 161–177 dipin per commit + cek versi; DroidSpaces dipaksa off); tidak ada yang di-port; #27 ditutup dengan alasan |
| W6 | P2 | Hemat CI: `paths-ignore` pada `validate.yml`; bersihkan `__pycache__` yang dilacak git. | **Selesai** 2026-10-15 — hanya trigger `push` yang mengabaikan `**.md`, `LICENSE`, `docs/**.png` (`docs/validation/*.json` tetap dicek karena dibaca kode; PR selalu dicek); test resolved-config kini ikut CI; 12 file `.pyc` dilepas + `.gitignore` |
| W7 | P3 | Hapus 22 branch lama milik PR #1–#26 yang sudah ditutup. | **Disetujui owner, menunggu eksekusi owner** — ke-22 ujung branch diverifikasi = head PR (`refs/pull/N/head` tetap menyimpan commit). Sesi ini hanya boleh push ke branch kerjanya (proxy 403), jadi hapus lewat GitHub → Branches atau perintah di bawah. `feat/optional-sublevel-disable-droidspaces` (PR #27) sengaja disimpan |
| W8 | P3 | Selaraskan nama workflow dengan file/isi (T7); putuskan hapus atau simpan workflow Telegram yang nonaktif. | **Selesai** 2026-10-15 — `cogan-smart-auto-update.yml` ("Cogan Manual Update", padahal hanya cek revisi read-only) → `upstream-revision-check.yml` "Upstream Revision Check (read-only)". Workflow Telegram tetap disimpan nonaktif sesuai keputusan PR #5; namanya sudah sesuai isi. Catatan: workflow ini sebagian tumpang-tindih dengan `root-upstream-provenance.yml` (kandidat penggabungan, belum dikerjakan) |
| W9 | P3 | Rapikan issue #2, #3 (roadmap) dan #19 (SUSFS): perbarui ringkasan status, tutup yang selesai. | **Selesai** 2026-10-15 — body ketiganya diganti checklist status; tidak ada yang layak ditutup (masih ada sisa pekerjaan) |
| W10 | P2 | Issue #3: catat SHA root manager & SUSFS yang benar-benar dipakai per build; usulan pin KernelSU/BakaSU. | **Selesai** 2026-10-15 — `ROOT_MANAGER_REPO/REF/SHA` + `SUSFS_SHA` masuk `build-env-*.txt`; ref tidak diubah. Usulan: KernelSU `v3.3.1` setelah 1 build sukses; BakaSU tetap `main` (tag stabil terlalu tua) |

## D. Bukti hijau (tidak perlu diulang)

- Validate run 405 (`38707353627`) pada `dev@70f5b30` — hijau.
- Main-patch-only SUSFS: run `38691986084`, job `116279761088` — hijau (lihat handoff).

## E. Checkpoint

- **2026-10-15** — Kesepakatan kerja & audit selesai. Berikutnya: **W1**.
- **2026-10-15** — W1 + W9 selesai (fix SUSFS fail-fast dan cek `.config` ketat kini ada di `dev`; issue #2/#3/#19 dirapikan). Berikutnya: **W2** (keputusan owner) lalu **W3**.
- **2026-10-15** — W3 + W4 selesai: patch BBG lolos cek; source direkonstruksi identik; `pahole` beres; config + gate + `make prepare` lulus. Berikutnya: keputusan owner untuk **W4b** (compile) dan patch `003`; tanpa itu lanjut **W6** (hemat CI).
- **2026-10-15** — W5 + W6 + W8 selesai. **PR #28 di-squash-merge ke `dev` (`c96f771`)**; PR #27 ditutup; issue #2/#19 diperbarui. Tidak ada PR terbuka. Berikutnya: keputusan owner **W4b** (compile + patch `003`), **W2**, **W7**.
- **2026-10-15** — PR #29 di-merge (W10). W2 diputuskan (`dev` utama). W7 disetujui, tapi penghapusan diblokir proxy sesi (403) → perlu dieksekusi owner. Compile W4b belum diizinkan. **Aturan tambahan:** setelah PR di-merge, `dev` di-merge ke branch kerja; tidak ada force-push (ruleset melarangnya).
- **2026-10-15** — Owner menetapkan: **kompilasi hanya manual oleh owner** (aturan A10). Tidak ada lagi pekerjaan yang menunggu Claude; sisa: W4b (owner compile), W7 (owner hapus branch), runtime test.

## F. Perintah hapus branch lama (W7, dijalankan owner)

```sh
git push origin --delete \
  fix/susfs-config-strict-issue-19 fix/susfs-patch-fail-fast-issue-19 \
  fix/ksun-pin-verified-tag fix/ksun-checkout-provenance fix/log-ksun-installed-revision \
  fix/root-installer-download-safety test/ksun-susfs-safety-gate ui/root-manager-first \
  feature/root-manager-dropdown ci/safer-mobile-build-defaults feature/cogan-build-identity \
  cleanup/remove-unused-nethunter-assets cleanup/remove-nethunter-wirelessksu \
  cleanup/remove-telegram-actions fix/release-success-gate fix/cache-release-build-order \
  ci/manual-upstream-provenance feat/upstream-provenance-collector \
  docs/root-manager-upstream-baseline test/root-matrix-regression \
  fix/disable-optional-notifications feature/ksun-optional-build
```

Semua branch diproteksi ruleset; bila ditolak, nonaktifkan sementara aturan *Restrict deletions* di Settings → Rules, atau hapus satu per satu di halaman Branches.

