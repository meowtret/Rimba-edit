# -*- coding: utf-8 -*-
"""Cek topologi untuk layer poligon dan garis.

Poligon : geometri tidak valid, tumpang tindih, celah (lubang di antara
          bidang), dan sliver (bidang terlalu kecil).
Garis   : geometri tidak valid, garis saling memotong (crossing), dangle.

Semua temuan ditulis ke layer sementara (memory) agar bisa ditinjau satu per
satu, dan fitur yang bermasalah dipilih (select) di layer asal. Perbaikan
otomatis hanya untuk geometri tidak valid (makeValid) dan bersifat opsional.
"""
from qgis.core import (
    QgsFeature, QgsGeometry, QgsLayerTreeLayer, QgsPointXY, QgsProject,
    QgsSpatialIndex, QgsSymbol, QgsVectorLayer,
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QPlainTextEdit, QVBoxLayout,
)

from ...core.utils import (
    ACCEPTED, AREA_M2, GEOM_LINE, GEOM_POINT, GEOM_POLYGON, Progress,
    area_calculator,
    edit_command, ensure_editable, exec_dialog, get_vector_layer,
    make_double_field, make_int_field, make_string_field, measure_area,
    polygon_only, repair_geometry, warn,
)

TITLE = 'Cek Topologi'


# --------------------------------------------------------------------------
# Logika pemeriksaan (tanpa GUI)
# --------------------------------------------------------------------------
class Findings:
    def __init__(self):
        self.invalid = []     # (fid, QgsPointXY|None, pesan)
        self.fixed = []       # fid
        self.overlaps = []    # (fid_a, fid_b, luas_m2, geom)
        self.gaps = []        # (luas_m2, geom)
        self.slivers = []     # (fid, luas_m2, geom)
        self.crossings = []   # (fid_a, fid_b, QgsPointXY)
        self.dangles = []     # (fid, QgsPointXY)
        self.cancelled = False

    def feature_ids(self):
        ids = {fid for fid, _, _ in self.invalid}
        ids.update(a for a, _, _, _ in self.overlaps)
        ids.update(b for _, b, _, _ in self.overlaps)
        ids.update(fid for fid, _, _ in self.slivers)
        ids.update(a for a, _, _ in self.crossings)
        ids.update(b for _, b, _ in self.crossings)
        ids.update(fid for fid, _ in self.dangles)
        return ids


def _invalid_location(geom):
    try:
        errors = geom.validateGeometry()
    except Exception:
        return None, 'Geometri tidak valid'
    for err in errors:
        where = err.where() if err.hasWhere() else None
        return (QgsPointXY(where) if where is not None else None), err.what()
    return None, 'Geometri tidak valid'


def _step(progress, i, label=None):
    if progress is None:
        return True
    return progress.step(i, label)


def check_validity(features, findings):
    """Kembalikan {fid: geometri_untuk_analisis} (yang tidak valid diperbaiki
    sementara agar operasi GEOS berikutnya tidak gagal)."""
    geoms = {}
    for f in features:
        if not f.hasGeometry() or f.geometry().isEmpty():
            continue
        g = f.geometry()
        if not g.isGeosValid():
            point, msg = _invalid_location(g)
            findings.invalid.append((f.id(), point, msg))
            fixed = g.makeValid()
            g = fixed if fixed and not fixed.isEmpty() else g
        geoms[f.id()] = g
    return geoms


def build_index(geoms):
    index = QgsSpatialIndex()
    for fid, g in geoms.items():
        feat = QgsFeature(fid)
        feat.setGeometry(g)
        index.addFeature(feat)
    return index


def check_polygons(geoms, da, opts, findings, progress=None):
    index = build_index(geoms)
    ids = sorted(geoms)
    n = len(ids)

    if opts.get('sliver'):
        limit = opts.get('sliver_m2', 1.0)
        for fid in ids:
            area = measure_area(da, geoms[fid], AREA_M2)
            if area < limit:
                findings.slivers.append((fid, area, geoms[fid]))

    if opts.get('overlap'):
        tol = opts.get('overlap_m2', 0.01)
        for i, fid in enumerate(ids):
            if i % 25 == 0 and not _step(progress, i, 'Memeriksa tumpang '
                                                      'tindih...'):
                findings.cancelled = True
                return
            g = geoms[fid]
            engine = QgsGeometry.createGeometryEngine(g.constGet())
            engine.prepareGeometry()
            for other in index.intersects(g.boundingBox()):
                if other <= fid:
                    continue
                g2 = geoms[other]
                if not engine.intersects(g2.constGet()):
                    continue
                inter = polygon_only(g.intersection(g2))
                if inter.isEmpty():
                    continue
                area = measure_area(da, inter, AREA_M2)
                if area > tol:
                    findings.overlaps.append((fid, other, area, inter))

    if opts.get('gap') and n > 0:
        _step(progress, n, 'Memeriksa celah...')
        union = QgsGeometry.unaryUnion([geoms[fid] for fid in ids])
        min_area = opts.get('gap_min_m2', 0.01)
        max_area = opts.get('gap_max_m2', 0.0)
        for part in union.asGeometryCollection():
            if part.type() != GEOM_POLYGON:
                continue
            rings = part.asPolygon()
            for ring in rings[1:]:
                hole = QgsGeometry.fromPolygonXY([ring])
                area = measure_area(da, hole, AREA_M2)
                if area < min_area:
                    continue
                if max_area and area > max_area:
                    continue
                findings.gaps.append((area, hole))


def _endpoints(geom):
    lines = geom.asMultiPolyline() if geom.isMultipart() \
        else [geom.asPolyline()]
    points = []
    for line in lines:
        if len(line) < 2:
            continue
        if line[0] == line[-1]:
            continue  # garis tertutup tidak punya ujung
        points.extend([line[0], line[-1]])
    return points


def check_lines(geoms, opts, findings, progress=None):
    index = build_index(geoms)
    ids = sorted(geoms)

    if opts.get('crossing'):
        for i, fid in enumerate(ids):
            if i % 25 == 0 and not _step(progress, i, 'Memeriksa '
                                                      'perpotongan...'):
                findings.cancelled = True
                return
            g = geoms[fid]
            for other in index.intersects(g.boundingBox()):
                if other <= fid:
                    continue
                g2 = geoms[other]
                if not g.crosses(g2):
                    continue
                inter = g.intersection(g2)
                for part in inter.asGeometryCollection():
                    if part.type() == GEOM_POINT:
                        for p in (part.asMultiPoint() if part.isMultipart()
                                  else [part.asPoint()]):
                            findings.crossings.append((fid, other,
                                                       QgsPointXY(p)))

    if opts.get('dangle'):
        tol = opts.get('dangle_tol', 0.0)
        for i, fid in enumerate(ids):
            if i % 25 == 0 and not _step(progress, i, 'Memeriksa dangle...'):
                findings.cancelled = True
                return
            for pt in _endpoints(geoms[fid]):
                pt_geom = QgsGeometry.fromPointXY(pt)
                rect = pt_geom.boundingBox()
                rect.grow(max(tol, 1e-9))
                connected = False
                for other in index.intersects(rect):
                    if other == fid:
                        # Ujung yang menyentuh bagian lain fitur yang sama
                        rest = geoms[fid]
                        others = [q for q in _endpoints(rest) if q != pt]
                        if any(QgsGeometry.fromPointXY(q).distance(pt_geom)
                               <= tol for q in others):
                            connected = True
                            break
                        continue
                    if geoms[other].distance(pt_geom) <= tol:
                        connected = True
                        break
                if not connected:
                    findings.dangles.append((fid, pt))


# --------------------------------------------------------------------------
# Layer hasil
# --------------------------------------------------------------------------
def _memory_layer(kind, name, crs):
    layer = QgsVectorLayer('{}?crs={}'.format(kind, crs.authid() or
                                              'EPSG:4326'), name, 'memory')
    layer.setCrs(crs)
    layer.dataProvider().addAttributes([
        make_string_field('jenis', 40),
        make_int_field('fid_a'),
        make_int_field('fid_b'),
        make_double_field('luas_m2', 20, 4),
        make_string_field('keterangan', 254),
    ])
    layer.updateFields()
    return layer


def _add(layer, geom, jenis, fid_a=None, fid_b=None, luas=None, ket=''):
    f = QgsFeature(layer.fields())
    g = QgsGeometry(geom)
    if layer.geometryType() == GEOM_POLYGON:
        g.convertToMultiType()
    f.setGeometry(g)
    f.setAttributes([jenis, fid_a, fid_b,
                     round(luas, 4) if luas is not None else None, ket])
    layer.dataProvider().addFeature(f)


def build_result_layers(source, findings):
    crs = source.crs()
    poly = _memory_layer('MultiPolygon', 'Galat area - ' + source.name(), crs)
    pts = _memory_layer('Point', 'Galat titik - ' + source.name(), crs)

    for a, b, area, g in findings.overlaps:
        _add(poly, g, 'Tumpang tindih', a, b, area)
    for area, g in findings.gaps:
        _add(poly, g, 'Celah', None, None, area)
    for fid, area, g in findings.slivers:
        _add(poly, g, 'Sliver / terlalu kecil', fid, None, area)
    for fid, point, msg in findings.invalid:
        if point is not None:
            status = 'diperbaiki' if fid in findings.fixed else 'belum'
            _add(pts, QgsGeometry.fromPointXY(point), 'Tidak valid', fid, None,
                 None, '{} ({})'.format(msg, status))
    for a, b, point in findings.crossings:
        _add(pts, QgsGeometry.fromPointXY(point), 'Perpotongan', a, b)
    for fid, point in findings.dangles:
        _add(pts, QgsGeometry.fromPointXY(point), 'Dangle', fid)

    for lyr, color in ((poly, '#e63946'), (pts, '#d00000')):
        symbol = QgsSymbol.defaultSymbol(lyr.geometryType())
        symbol.setColor(QColor(color))
        if lyr is poly:
            symbol.setOpacity(0.6)
        else:
            try:
                symbol.setSize(3.2)
            except Exception:
                pass
        lyr.renderer().setSymbol(symbol)
    return [lyr for lyr in (poly, pts) if lyr.featureCount() > 0]


def add_layers_to_project(layers, source):
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    group_name = 'Cek Topologi - {}'.format(source.name())
    old = root.findGroup(group_name)
    if old is not None:
        root.removeChildNode(old)
    group = root.insertGroup(0, group_name)
    for layer in layers:
        project.addMapLayer(layer, False)
        group.addChildNode(QgsLayerTreeLayer(layer))


def summary(findings, is_polygon, opts):
    lines = []
    lines.append('Geometri tidak valid : {}{}'.format(
        len(findings.invalid),
        ' ({} diperbaiki otomatis)'.format(len(findings.fixed))
        if findings.fixed else ''))
    if is_polygon:
        if opts.get('overlap'):
            total = sum(a for _, _, a, _ in findings.overlaps)
            lines.append('Tumpang tindih       : {} pasang ({:,.2f} m²)'.format(
                len(findings.overlaps), total))
        if opts.get('gap'):
            total = sum(a for a, _ in findings.gaps)
            lines.append('Celah                : {} ({:,.2f} m²)'.format(
                len(findings.gaps), total))
        if opts.get('sliver'):
            lines.append('Sliver (< {} m²)     : {}'.format(
                opts.get('sliver_m2'), len(findings.slivers)))
    else:
        if opts.get('crossing'):
            lines.append('Perpotongan garis    : {}'.format(
                len(findings.crossings)))
        if opts.get('dangle'):
            lines.append('Dangle               : {}'.format(
                len(findings.dangles)))
    if findings.cancelled:
        lines.append('\nPemeriksaan DIBATALKAN, hasil belum lengkap.')
    lines.append('')
    lines.append('Catatan:')
    if is_polygon:
        lines.append('- Celah = lubang yang dikelilingi bidang. Celah di tepi '
                     'luar (tidak tertutup) tidak terdeteksi.')
        lines.append('- Tumpang tindih & celah perlu diperbaiki manual, '
                     'mis. dengan snapping atau Vertex Tool.')
    else:
        lines.append('- Dangle di batas luar jaringan bisa jadi wajar.')
    lines.append('- Fitur bermasalah sudah TERPILIH di layer asal; '
                 'lokasi galat ada di grup layer "Cek Topologi".')
    return '\n'.join(lines)


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
class TopologyDialog(QDialog):
    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumWidth(440)
        self.is_polygon = layer.geometryType() == GEOM_POLYGON
        layout = QVBoxLayout(self)

        group = QGroupBox('Aturan yang diperiksa')
        form = QFormLayout(group)
        self.chk_valid = QCheckBox('Geometri tidak valid (selalu diperiksa)')
        self.chk_valid.setChecked(True)
        self.chk_valid.setEnabled(False)
        form.addRow(self.chk_valid)
        self.chk_fix = QCheckBox('Perbaiki otomatis geometri tidak valid '
                                 '(makeValid)')
        form.addRow(self.chk_fix)

        if self.is_polygon:
            self.chk_overlap = QCheckBox('Tumpang tindih')
            self.chk_overlap.setChecked(True)
            self.overlap_tol = self._spin(0.01, 3)
            form.addRow(self.chk_overlap)
            form.addRow('   abaikan bila luas ≤ (m²):', self.overlap_tol)
            self.chk_gap = QCheckBox('Celah di antara bidang')
            self.chk_gap.setChecked(True)
            self.gap_min = self._spin(0.01, 3)
            self.gap_max = self._spin(0.0, 2, 1e12)
            form.addRow(self.chk_gap)
            form.addRow('   luas minimum celah (m²):', self.gap_min)
            form.addRow('   luas maksimum (m², 0 = tanpa batas):', self.gap_max)
            self.chk_sliver = QCheckBox('Sliver / bidang terlalu kecil')
            self.chk_sliver.setChecked(True)
            self.sliver = self._spin(1.0, 3)
            form.addRow(self.chk_sliver)
            form.addRow('   batas luas (m²):', self.sliver)
        else:
            unit = layer.crs().mapUnits()
            try:
                from qgis.core import QgsUnitTypes
                unit_name = QgsUnitTypes.toString(unit)
            except Exception:
                unit_name = 'satuan CRS'
            self.chk_cross = QCheckBox('Garis saling memotong (crossing)')
            self.chk_cross.setChecked(True)
            form.addRow(self.chk_cross)
            self.chk_dangle = QCheckBox('Dangle (ujung garis menggantung)')
            self.chk_dangle.setChecked(True)
            self.dangle_tol = self._spin(0.0, 6)
            form.addRow(self.chk_dangle)
            form.addRow('   toleransi sambung ({}):'.format(unit_name),
                        self.dangle_tol)
        layout.addWidget(group)

        n_sel = layer.selectedFeatureCount()
        self.selected_only = QCheckBox('Hanya bidang terpilih ({})'.format(
            n_sel))
        self.selected_only.setChecked(n_sel > 0)
        self.selected_only.setEnabled(n_sel > 0)
        layout.addWidget(self.selected_only)
        self.make_layers = QCheckBox('Buat layer hasil untuk ditinjau')
        self.make_layers.setChecked(True)
        layout.addWidget(self.make_layers)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _spin(value, decimals, maximum=1e9):
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setRange(0.0, maximum)
        spin.setValue(value)
        return spin

    def options(self):
        if self.is_polygon:
            return {
                'overlap': self.chk_overlap.isChecked(),
                'overlap_m2': self.overlap_tol.value(),
                'gap': self.chk_gap.isChecked(),
                'gap_min_m2': self.gap_min.value(),
                'gap_max_m2': self.gap_max.value(),
                'sliver': self.chk_sliver.isChecked(),
                'sliver_m2': self.sliver.value(),
            }
        return {
            'crossing': self.chk_cross.isChecked(),
            'dangle': self.chk_dangle.isChecked(),
            'dangle_tol': self.dangle_tol.value(),
        }


class ReportDialog(QDialog):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Hasil ' + TITLE)
        self.setMinimumSize(480, 340)
        layout = QVBoxLayout(self)
        box = QPlainTextEdit(text)
        box.setReadOnly(True)
        font = box.font()
        font.setFamily('Consolas')
        box.setFont(font)
        layout.addWidget(box)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class TopologyChecker:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        layer = get_vector_layer(self.iface, TITLE, (GEOM_POLYGON, GEOM_LINE))
        if not layer:
            return
        dialog = TopologyDialog(layer, self.iface.mainWindow())
        if exec_dialog(dialog) != ACCEPTED:
            return
        opts = dialog.options()
        is_polygon = dialog.is_polygon

        features = layer.selectedFeatures() if dialog.selected_only.isChecked() \
            else list(layer.getFeatures())
        if not features:
            warn(TITLE, 'Tidak ada fitur untuk diperiksa.')
            return

        findings = Findings()
        progress = Progress(TITLE, 'Memeriksa validitas geometri...',
                            len(features))
        geoms = check_validity(features, findings)

        if dialog.chk_fix.isChecked() and findings.invalid:
            if ensure_editable(layer, TITLE):
                originals = {f.id(): f.geometry() for f in features}
                with edit_command(layer, 'Perbaiki geometri tidak valid'):
                    for fid, _, _ in findings.invalid:
                        fixed = repair_geometry(originals[fid], layer)
                        if fixed is not None and fixed.isGeosValid() and \
                                layer.changeGeometry(fid, fixed):
                            findings.fixed.append(fid)
                            geoms[fid] = fixed

        try:
            if is_polygon:
                da, _ = area_calculator(layer)
                check_polygons(geoms, da, opts, findings, progress)
            else:
                check_lines(geoms, opts, findings, progress)
        finally:
            progress.close()

        if dialog.make_layers.isChecked():
            result_layers = build_result_layers(layer, findings)
            if result_layers:
                add_layers_to_project(result_layers, layer)

        problem_ids = findings.feature_ids() - set(findings.fixed)
        layer.selectByIds(sorted(problem_ids))
        self.iface.setActiveLayer(layer)
        exec_dialog(ReportDialog(summary(findings, is_polygon, opts),
                                 self.iface.mainWindow()))
