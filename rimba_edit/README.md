# Rimba Edit

Plugin QGIS untuk edit **bidang dan atribut**: petak, blok, areal izin, persil.
Plugin ini mendukung QGIS 3.22 sampai QGIS 4.x.

## Daftar alat

Menu: **Vector → Rimba Edit**. Alat-alat utama juga tersedia di toolbar *Rimba Edit*.

| Grup | Alat | Fungsi |
|---|---|---|
| Geometri | Pecah Multipart | Memecah fitur multipart terpilih menjadi beberapa fitur. Bagian pertama tetap memakai fid asli. |
| | Perbaiki Geometri Tidak Valid | Memperbaiki geometri tidak valid dengan `makeValid`. Hanya fitur yang benar-benar tidak valid yang diubah. |
| Atribut | Salin Atribut ke Pilihan | Menyalin kolom terpilih dari 1 bidang sumber ke bidang lain. |
| | Isi Kolom Cepat | Mengisi beberapa kolom sekaligus. Nilai diperiksa sesuai tipe kolom. Ketik `NULL` untuk mengosongkan. |
| | Cari & Ganti Nilai | Mencari dan mengganti teks pada kolom teks, dengan opsi beda huruf besar/kecil atau seluruh isi kolom. |
| | Salin Koordinat Bidang | Menyalin koordinat ke clipboard dalam CRS layer, WGS84 desimal, atau WGS84 DMS. Siap ditempel ke Excel. |
| Bidang & Luas | Hitung Luas | Menghitung luas ellipsoidal dalam ha atau m², ke kolom yang ada atau ke kolom baru. |
| | Validasi Kolom Wajib | Menyorot bidang yang kolom wajibnya kosong. Gaya asli layer tetap tersimpan. |
| | Ekspor Atribut ke Excel | Ekspor ke .xlsx (huruf Arial, header berwarna) dengan opsi kolom luas hitungan. |
| Topologi | Cek Topologi | Poligon: tidak valid, tumpang tindih, celah, sliver. Garis: tidak valid, perpotongan, dangle. Temuan ditulis ke layer hasil. |

Setiap alat dicatat sebagai **satu langkah undo** (Ctrl+Z). Perubahan baru tersimpan
setelah Ian menyimpan edit layer.

## Pemasangan

1. QGIS → **Plugins → Manage and Install Plugins → Install from ZIP**.
2. Pilih `rimba_edit-0.9.2.zip`, lalu klik **Install Plugin**.
3. Kalau plugin *Editor Bidang dan Atribut* versi lama masih aktif, matikan dulu supaya toolbar tidak dobel.

## Asal-usul dan lisensi

Plugin ini adalah karya turunan (fork) dari **Editor Bidang dan Atribut** v0.1.1
karya **Fajar SNI** (https://github.com/fajarSNI/editor-bidang-dan-atribut),
berlisensi GNU GPL v3.

Dimodifikasi sejak 2 November 2026 oleh Alfian (Ian). Perubahan utama dibandingkan versi asal:

- Bisa dimuat di Python 3.9+. Versi asal gagal dimuat di Python < 3.12 karena penulisan f-string multi-baris.
- Kompatibel Qt5 dan Qt6 (QGIS 3 dan QGIS 4).
- Kolom ID utama (fid GeoPackage, PK PostGIS) tidak lagi ikut disalin atau ditukar. Galat *UNIQUE constraint* / *duplicate key* saat menyimpan sudah diatasi.
- Mendukung geometri Z/M dan menyesuaikan otomatis dengan tipe single/multipart layer.
- Nilai NULL ditangani dengan benar di Validasi dan Ekspor Excel.
- Cek Topologi ditulis ulang:
  - Memakai indeks spasial.
  - Celah dideteksi dari lubang hasil gabungan bidang, bukan dari *convex hull*.
  - Temuan ditulis ke layer hasil.
  - Ada deteksi dangle.
- Alat Tukar Atribut, Pemecahan Bidang, dan Penomoran Akhiran Otomatis dihapus.
- Alat "Tutup Poligon Otomatis" diganti dengan "Perbaiki Geometri Tidak Valid", yang hanya mengubah fitur yang benar-benar tidak valid.

Rimba Edit dirilis di bawah lisensi yang sama, **GNU GPL v3 atau yang lebih baru**
(lihat `LICENSE`). Kalau disebarluaskan, sertakan kode sumbernya dan pertahankan
atribusi di atas.
