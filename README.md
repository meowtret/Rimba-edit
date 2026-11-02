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

Setiap alat dicatat sebagai **satu langkah undo** (Ctrl+Z). Kolom ID utama (fid
GeoPackage, PK PostGIS) tidak pernah ikut disalin, sehingga tidak ada galat
*UNIQUE constraint* saat menyimpan.

## Pemasangan

1. Unduh ZIP terbaru dari halaman **Releases**, atau buat sendiri dengan `python build_zip.py` (hasilnya ada di `dist/`).
2. Di QGIS buka **Plugins → Manage and Install Plugins → Install from ZIP**, pilih file ZIP, lalu klik **Install Plugin**.

## Struktur repositori

```
rimba_edit/          folder plugin (yang dikemas ke ZIP)
  core/utils.py      helper bersama: kompatibilitas QGIS 3/4, PK, NULL, undo, luas
  tools/             setiap alat dalam satu modul
  icons/             ikon SVG bergaya tema bawaan QGIS
tests/test_rimba.py  uji fungsional dengan QGIS headless
build_zip.py         pengemas ZIP
```

## Pengembangan

Uji fungsional dijalankan dengan Python milik QGIS (butuh `python3-qgis`):

```
QT_QPA_PLATFORM=offscreen python3 tests/test_rimba.py
```

## Asal-usul dan lisensi

Plugin ini adalah karya turunan (fork) dari **Editor Bidang dan Atribut** v0.1.1
karya **Fajar SNI** (https://github.com/fajarSNI/editor-bidang-dan-atribut),
berlisensi GNU GPL v3. Dimodifikasi sejak 2 November 2026 oleh Alfian (Ian).
Riwayat perubahannya ada di `rimba_edit/metadata.txt`.

Rimba Edit dirilis di bawah lisensi **GNU GPL v3 atau yang lebih baru** (lihat `LICENSE`).
