# -*- coding: utf-8 -*-
"""
Rimba Edit - utilitas bersama.

Dikembangkan dari "Editor Bidang dan Atribut" (c) Fajar SNI, GPL-3.0.
Dimodifikasi 2026 oleh Alfian (Ian). Lisensi: GPL-3.0-or-later.

Semua perbedaan API antara QGIS 3.x (Qt5) dan QGIS 4.x (Qt6) dikumpulkan
di sini supaya alat-alat lain cukup memakai konstanta/helper dari modul ini.
"""
import re
from contextlib import contextmanager

from qgis.core import (
    Qgis,
    QgsDistanceArea,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProject,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsVectorLayerUtils,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, QDate, QDateTime, QTime, Qt
from qgis.PyQt.QtWidgets import QDialog, QMessageBox, QProgressDialog

PLUGIN_NAME = 'Rimba Edit'


# --------------------------------------------------------------------------
# Kompatibilitas enum QGIS 3 / QGIS 4
# --------------------------------------------------------------------------
def _first(*getters):
    for getter in getters:
        try:
            return getter()
        except AttributeError:
            continue
    raise AttributeError('Tidak ada enum yang cocok untuk versi QGIS ini')


# Nama baru (QGIS >= 3.30, satu-satunya yang ada di QGIS 4) dicoba lebih dulu.
# Cadangan untuk QGIS 3.22-3.28 ditulis dalam bentuk ber-scope
# (Kelas.NamaEnum.Anggota) yang juga valid di PyQt5.
GEOM_POINT = _first(lambda: Qgis.GeometryType.Point,
                    lambda: QgsWkbTypes.GeometryType.PointGeometry)
GEOM_LINE = _first(lambda: Qgis.GeometryType.Line,
                   lambda: QgsWkbTypes.GeometryType.LineGeometry)
GEOM_POLYGON = _first(lambda: Qgis.GeometryType.Polygon,
                      lambda: QgsWkbTypes.GeometryType.PolygonGeometry)

AREA_M2 = _first(lambda: Qgis.AreaUnit.SquareMeters,
                 lambda: QgsUnitTypes.AreaUnit.AreaSquareMeters)
AREA_HA = _first(lambda: Qgis.AreaUnit.Hectares,
                 lambda: QgsUnitTypes.AreaUnit.AreaHectares)

ORIGIN_PROVIDER = _first(lambda: Qgis.FieldOrigin.Provider,
                         lambda: QgsFields.FieldOrigin.OriginProvider)
ORIGIN_EDIT = _first(lambda: Qgis.FieldOrigin.Edit,
                     lambda: QgsFields.FieldOrigin.OriginEdit)

REQUEST_NO_GEOMETRY = _first(
    lambda: Qgis.FeatureRequestFlag.NoGeometry,
    lambda: QgsFeatureRequest.Flag.NoGeometry)

MSG_INFO = Qgis.MessageLevel.Info
MSG_WARNING = Qgis.MessageLevel.Warning
MSG_SUCCESS = Qgis.MessageLevel.Success

YES = QMessageBox.StandardButton.Yes
NO = QMessageBox.StandardButton.No
ACCEPTED = QDialog.DialogCode.Accepted


def exec_dialog(dialog):
    """Jalankan dialog modal (exec() tersedia di PyQt5 dan PyQt6)."""
    return dialog.exec()


# --------------------------------------------------------------------------
# Pesan
# --------------------------------------------------------------------------
def push(iface, text, level=MSG_INFO, duration=6):
    iface.messageBar().pushMessage(PLUGIN_NAME, text, level=level,
                                   duration=duration)


def warn(title, text, parent=None):
    QMessageBox.warning(parent, title, text)


def info(title, text, parent=None):
    QMessageBox.information(parent, title, text)


def ask(title, text, parent=None):
    reply = QMessageBox.question(parent, title, text, YES | NO, NO)
    return reply == YES


# --------------------------------------------------------------------------
# Validasi layer
# --------------------------------------------------------------------------
def get_vector_layer(iface, title, geom_types=None):
    """Kembalikan layer aktif bila berupa layer vektor (dan tipenya cocok)."""
    layer = iface.activeLayer()
    if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
        warn(title, 'Pilih (aktifkan) layer vektor terlebih dahulu.')
        return None
    if geom_types is not None and layer.geometryType() not in geom_types:
        names = []
        if GEOM_POLYGON in geom_types:
            names.append('poligon')
        if GEOM_LINE in geom_types:
            names.append('garis')
        if GEOM_POINT in geom_types:
            names.append('titik')
        warn(title, 'Alat ini hanya untuk layer {}.'.format(' / '.join(names)))
        return None
    return layer


def ensure_editable(layer, title, parent=None):
    """Pastikan layer dalam mode edit. True bila siap diedit."""
    if layer.isEditable():
        return True
    if not ask(title, 'Layer "{}" belum dalam mode edit.\n'
               'Aktifkan mode edit sekarang?'.format(layer.name()), parent):
        return False
    if not layer.startEditing():
        warn(title, 'Layer ini tidak dapat diedit (read-only).', parent)
        return False
    return True


@contextmanager
def edit_command(layer, text):
    """Kelompokkan semua perubahan menjadi SATU langkah undo (Ctrl+Z)."""
    layer.beginEditCommand(text)
    try:
        yield
    except Exception:
        layer.destroyEditCommand()
        raise
    else:
        layer.endEditCommand()


# --------------------------------------------------------------------------
# Kolom
# --------------------------------------------------------------------------
def pk_indexes(layer):
    """Indeks kolom kunci utama (mis. fid GeoPackage, id serial PostGIS)."""
    try:
        return set(layer.primaryKeyAttributes())
    except Exception:
        return set()


def writable_field_indexes(layer, exclude_pk=True):
    """Indeks kolom yang aman ditulis: bukan kolom virtual/join, bukan PK."""
    fields = layer.fields()
    pks = pk_indexes(layer) if exclude_pk else set()
    result = []
    for i in range(fields.count()):
        if i in pks:
            continue
        if fields.fieldOrigin(i) not in (ORIGIN_PROVIDER, ORIGIN_EDIT):
            continue
        result.append(i)
    return result


def is_text_field(field):
    if field.isNumeric():
        return False
    type_name = (field.typeName() or '').lower()
    if any(key in type_name for key in ('char', 'text', 'string')):
        return True
    try:
        return int(field.type()) == 10  # QVariant::String / QMetaType::QString
    except Exception:
        return False


def is_integer_field(field):
    type_name = (field.typeName() or '').lower()
    return field.isNumeric() and 'int' in type_name


def make_double_field(name, length=20, precision=4):
    """Buat QgsField bertipe double (API berbeda sejak QGIS 3.38)."""
    try:
        from qgis.PyQt.QtCore import QMetaType
        return QgsField(name, QMetaType.Type.Double, 'double', length,
                        precision)
    except Exception:
        from qgis.PyQt.QtCore import QVariant
        return QgsField(name, QVariant.Double, 'double', length, precision)


def make_string_field(name, length=254):
    try:
        from qgis.PyQt.QtCore import QMetaType
        return QgsField(name, QMetaType.Type.QString, 'string', length)
    except Exception:
        from qgis.PyQt.QtCore import QVariant
        return QgsField(name, QVariant.String, 'string', length)


def make_int_field(name):
    try:
        from qgis.PyQt.QtCore import QMetaType
        return QgsField(name, QMetaType.Type.LongLong, 'integer64')
    except Exception:
        from qgis.PyQt.QtCore import QVariant
        return QgsField(name, QVariant.LongLong, 'integer64')


# --------------------------------------------------------------------------
# Nilai
# --------------------------------------------------------------------------
def is_null(value):
    """True bila nilai atribut kosong/NULL.

    Di PyQGIS (Qt5) nilai NULL berupa QVariant, BUKAN None, sehingga
    pemeriksaan `value is None` saja tidak cukup.
    """
    if value is None:
        return True
    is_null_fn = getattr(value, 'isNull', None)
    if callable(is_null_fn):
        try:
            return bool(is_null_fn())
        except Exception:
            return False
    return False


def is_blank(value):
    return is_null(value) or (isinstance(value, str) and not value.strip())


def to_text(value):
    return '' if is_null(value) else str(value)


def to_python(value):
    """Ubah nilai atribut QGIS menjadi tipe Python biasa (untuk Excel, dsb.)."""
    if is_null(value):
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, QDateTime):
        return value.toPyDateTime()
    if isinstance(value, QDate):
        return value.toPyDate()
    if isinstance(value, QTime):
        return value.toPyTime()
    return str(value)


ID_CANDIDATES = ('NIB', 'NOMOR', 'NO_BIDANG', 'NO_PETAK', 'PETAK', 'NOP',
                 'KODE', 'NAMA', 'ID')


def feature_label(layer, feature):
    """Label singkat sebuah fitur untuk ditampilkan di daftar pilihan."""
    names_upper = {f.name().upper(): f.name() for f in layer.fields()}
    for cand in ID_CANDIDATES:
        name = names_upper.get(cand)
        if name and not is_blank(feature[name]):
            return 'FID {} - {}: {}'.format(feature.id(), name, feature[name])
    return 'FID {}'.format(feature.id())


# --------------------------------------------------------------------------
# Geometri
# --------------------------------------------------------------------------
def polygon_only(geom):
    """Ambil hanya bagian poligon dari hasil makeValid/intersection."""
    if geom is None or geom.isEmpty():
        return QgsGeometry()
    if geom.type() == GEOM_POLYGON:
        return geom
    parts = [p for p in geom.asGeometryCollection()
             if p.type() == GEOM_POLYGON and not p.isEmpty()]
    if not parts:
        return QgsGeometry()
    if len(parts) == 1:
        return parts[0]
    return QgsGeometry.collectGeometry(parts)


def line_only(geom):
    if geom is None or geom.isEmpty():
        return QgsGeometry()
    if geom.type() == GEOM_LINE:
        return geom
    parts = [p for p in geom.asGeometryCollection()
             if p.type() == GEOM_LINE and not p.isEmpty()]
    if not parts:
        return QgsGeometry()
    if len(parts) == 1:
        return parts[0]
    return QgsGeometry.collectGeometry(parts)


def fit_geometry(geom, layer):
    """Sesuaikan geometri dengan tipe layer (single/multi, Z/M).

    Kembalikan None bila tidak mungkin, mis. hasil multipart (2+ bagian)
    sedangkan layer bertipe singlepart.
    """
    if geom is None or geom.isEmpty():
        return None
    target = layer.wkbType()
    try:
        result = QgsGeometry(geom).coerceToType(target)
    except Exception:
        result = None
    if result:
        if len(result) == 1 and not result[0].isEmpty():
            return result[0]
        return None
    # Cadangan untuk QGIS lama
    g = QgsGeometry(geom)
    if QgsWkbTypes.isMultiType(target):
        g.convertToMultiType()
    elif g.isMultipart():
        if len(g.asGeometryCollection()) > 1:
            return None
        g.convertToSingleType()
    return g


def repair_geometry(geom, layer):
    """makeValid() lalu kembalikan ke tipe geometri layer. None bila gagal."""
    fixed = geom.makeValid()
    if fixed is None or fixed.isEmpty():
        return None
    if layer.geometryType() == GEOM_POLYGON:
        fixed = polygon_only(fixed)
    elif layer.geometryType() == GEOM_LINE:
        fixed = line_only(fixed)
    return fit_geometry(fixed, layer)


def create_feature(layer, geom, attributes):
    """Buat fitur baru yang aman terhadap PK/kolom unik.

    `attributes` berupa {indeks_kolom: nilai}. Kolom PK yang tidak diisi
    akan diisi otomatis oleh provider (GeoPackage, PostGIS, SpatiaLite).
    """
    context = layer.createExpressionContext()
    return QgsVectorLayerUtils.createFeature(layer, geom, attributes, context)


def copy_attributes_for_new(layer, feature):
    """Atribut fitur (tanpa PK & kolom virtual) untuk fitur turunan."""
    return {i: feature.attribute(i) for i in writable_field_indexes(layer)}


# --------------------------------------------------------------------------
# Luas
# --------------------------------------------------------------------------
def area_calculator(layer):
    """QgsDistanceArea yang hasilnya selalu dapat dikonversi ke m²/ha.

    Bila ellipsoid proyek 'NONE' dan CRS layer geografis (derajat), hasil
    planar dalam derajat persegi tidak bermakna, jadi dipakai WGS84.
    Mengembalikan (da, catatan) - catatan berisi teks peringatan atau ''.
    """
    project = QgsProject.instance()
    da = QgsDistanceArea()
    da.setSourceCrs(layer.crs(), project.transformContext())
    ellipsoid = project.ellipsoid()
    note = ''
    if (not ellipsoid or ellipsoid.upper() == 'NONE') and \
            layer.crs().isGeographic():
        ellipsoid = 'EPSG:7030'
        note = ('Ellipsoid proyek "None" dan CRS layer geografis; '
                'luas dihitung dengan ellipsoid WGS84.')
    da.setEllipsoid(ellipsoid or 'NONE')
    return da, note


def measure_area(da, geom, unit):
    return da.convertAreaMeasurement(da.measureArea(geom), unit)


# --------------------------------------------------------------------------
# Progress
# --------------------------------------------------------------------------
class Progress:
    """Dialog progres sederhana yang bisa dibatalkan."""

    def __init__(self, title, label, maximum, parent=None):
        self.dialog = QProgressDialog(label, 'Batal', 0, max(1, maximum),
                                      parent)
        self.dialog.setWindowTitle(title)
        self.dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.dialog.setMinimumDuration(400)
        self.dialog.setValue(0)

    def step(self, value, label=None):
        if label:
            self.dialog.setLabelText(label)
        self.dialog.setValue(value)
        QCoreApplication.processEvents()
        return not self.dialog.wasCanceled()

    def close(self):
        self.dialog.setValue(self.dialog.maximum())
        self.dialog.close()


def safe_sheet_name(name):
    clean = re.sub(r'[\\/*?:\[\]]', '_', name or '').strip()
    return (clean or 'Data')[:31]
