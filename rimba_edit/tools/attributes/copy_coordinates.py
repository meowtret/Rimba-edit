# -*- coding: utf-8 -*-
"""Salin koordinat titik tengah bidang terpilih ke clipboard (tab-separated,
siap ditempel ke Excel)."""
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject,
)
from qgis.PyQt.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QVBoxLayout,
)

from ...core.utils import (
    ACCEPTED, MSG_SUCCESS, exec_dialog, feature_label, get_vector_layer, push,
    warn,
)

TITLE = 'Salin Koordinat'


def _dms(value, positive, negative):
    hemi = positive if value >= 0 else negative
    value = abs(value)
    deg = int(value)
    minutes_full = (value - deg) * 60
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60
    if seconds >= 59.995:
        seconds = 0.0
        minutes += 1
    if minutes == 60:
        minutes = 0
        deg += 1
    return '{}°{:02d}\'{:05.2f}"{}'.format(deg, minutes, seconds, hemi)


class CoordDialog(QDialog):
    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.point = QComboBox()
        self.point.addItem('Titik di dalam bidang (point on surface)',
                           'surface')
        self.point.addItem('Centroid (bisa jatuh di luar bidang cekung)',
                           'centroid')
        self.crs = QComboBox()
        self.crs.addItem('CRS layer ({})'.format(layer.crs().authid()),
                         'layer')
        self.crs.addItem('WGS 84 - derajat desimal', 'dd')
        self.crs.addItem('WGS 84 - derajat menit detik', 'dms')
        form.addRow('Titik:', self.point)
        form.addRow('Sistem koordinat:', self.crs)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class CopyCoordinates:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        layer = get_vector_layer(self.iface, TITLE)
        if not layer:
            return
        selected = [f for f in layer.selectedFeatures() if f.hasGeometry()]
        if not selected:
            warn(TITLE, 'Pilih bidang terlebih dahulu.')
            return
        dialog = CoordDialog(layer, self.iface.mainWindow())
        if exec_dialog(dialog) != ACCEPTED:
            return
        mode = dialog.crs.currentData()
        use_surface = dialog.point.currentData() == 'surface'

        transform = None
        if mode in ('dd', 'dms'):
            transform = QgsCoordinateTransform(
                layer.crs(), QgsCoordinateReferenceSystem('EPSG:4326'),
                QgsProject.instance())
            header = 'Bidang\tBujur\tLintang'
        else:
            header = 'Bidang\tX\tY'
        geographic = mode in ('dd', 'dms') or layer.crs().isGeographic()
        decimals = 6 if geographic else 2

        lines = [header]
        for feature in selected:
            geom = feature.geometry()
            pt_geom = geom.pointOnSurface() if use_surface else geom.centroid()
            pt = pt_geom.asPoint()
            if transform is not None:
                pt = transform.transform(pt)
            if mode == 'dms':
                x, y = _dms(pt.x(), 'BT', 'BB'), _dms(pt.y(), 'LU', 'LS')
            else:
                x = '{:.{}f}'.format(pt.x(), decimals)
                y = '{:.{}f}'.format(pt.y(), decimals)
            lines.append('{}\t{}\t{}'.format(feature_label(layer, feature),
                                             x, y))

        QApplication.clipboard().setText('\n'.join(lines))
        push(self.iface, 'Koordinat {} bidang disalin ke clipboard (siap '
                         'ditempel ke Excel).'.format(len(selected)),
             MSG_SUCCESS)
