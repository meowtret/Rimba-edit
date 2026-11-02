# -*- coding: utf-8 -*-
"""Hitung luas ellipsoidal (ha atau m²) ke sebuah kolom, atau kolom baru."""
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLineEdit, QSpinBox, QVBoxLayout,
)

from ...core.utils import (
    ACCEPTED, AREA_HA, AREA_M2, GEOM_POLYGON, MSG_SUCCESS, MSG_WARNING,
    Progress, area_calculator, edit_command, ensure_editable, exec_dialog,
    get_vector_layer, is_integer_field, make_double_field, measure_area, push,
    warn, writable_field_indexes,
)

TITLE = 'Hitung Luas'
NEW_FIELD = '__new__'


class LuasDialog(QDialog):
    def __init__(self, layer, has_selection, note, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        fields = layer.fields()

        self.unit = QComboBox()
        self.unit.addItem('Hektare (ha)', 'ha')
        self.unit.addItem('Meter persegi (m²)', 'm2')

        self.field = QComboBox()
        self.field.addItem('+ Buat kolom baru', NEW_FIELD)
        for i in writable_field_indexes(layer):
            fld = fields.at(i)
            if fld.isNumeric():
                self.field.addItem(fld.name(), i)
                if 'LUAS' in fld.name().upper() and \
                        self.field.currentIndex() == 0:
                    self.field.setCurrentIndex(self.field.count() - 1)
                    if 'M2' in fld.name().upper():
                        self.unit.setCurrentIndex(1)

        self.new_name = QLineEdit('LUAS_HA')
        self.new_name.setMaxLength(10 if layer.providerType() == 'ogr' and
                                   layer.source().lower().split('|')[0]
                                   .endswith('.shp') else 63)
        self.decimals = QSpinBox()
        self.decimals.setRange(0, 6)
        self.decimals.setValue(4)

        form.addRow('Satuan:', self.unit)
        form.addRow('Kolom target:', self.field)
        form.addRow('Nama kolom baru:', self.new_name)
        form.addRow('Desimal:', self.decimals)
        layout.addLayout(form)

        self.selected_only = QCheckBox('Hanya bidang terpilih')
        self.selected_only.setChecked(has_selection)
        self.selected_only.setEnabled(has_selection)
        layout.addWidget(self.selected_only)

        ell = QLabel('Metode: luas ellipsoidal ({}).{}'.format(
            'ellipsoid proyek', '\n' + note if note else ''))
        ell.setWordWrap(True)
        ell.setStyleSheet('color: gray;')
        layout.addWidget(ell)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.field.currentIndexChanged.connect(self._toggle)
        self.unit.currentIndexChanged.connect(self._unit_changed)
        self._toggle()

    def _toggle(self, *args):
        self.new_name.setEnabled(self.field.currentData() == NEW_FIELD)

    def _unit_changed(self, *args):
        ha = self.unit.currentData() == 'ha'
        self.decimals.setValue(4 if ha else 2)
        if self.new_name.text() in ('LUAS_HA', 'LUAS_M2'):
            self.new_name.setText('LUAS_HA' if ha else 'LUAS_M2')


class HitungLuas:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        layer = get_vector_layer(self.iface, TITLE, (GEOM_POLYGON,))
        if not layer:
            return
        da, note = area_calculator(layer)
        has_sel = layer.selectedFeatureCount() > 0
        dialog = LuasDialog(layer, has_sel, note, self.iface.mainWindow())
        if exec_dialog(dialog) != ACCEPTED:
            return
        if not ensure_editable(layer, TITLE):
            return

        unit = AREA_HA if dialog.unit.currentData() == 'ha' else AREA_M2
        decimals = dialog.decimals.value()
        target = dialog.field.currentData()

        if target == NEW_FIELD:
            name = dialog.new_name.text().strip()
            if not name:
                warn(TITLE, 'Nama kolom baru tidak boleh kosong.')
                return
            if layer.fields().indexOf(name) >= 0:
                warn(TITLE, 'Kolom "{}" sudah ada. Pilih kolom tersebut dari '
                            'daftar atau gunakan nama lain.'.format(name))
                return
            if not layer.addAttribute(make_double_field(name, 20, decimals)):
                warn(TITLE, 'Gagal menambah kolom "{}".'.format(name))
                return
            idx = layer.fields().indexOf(name)
        else:
            idx = target
        as_int = is_integer_field(layer.fields().at(idx))

        if dialog.selected_only.isChecked():
            features = layer.selectedFeatures()
            total = len(features)
        else:
            features = layer.getFeatures()
            total = layer.featureCount()

        progress = Progress(TITLE, 'Menghitung luas...', total)
        count = 0
        total_area = 0.0
        with edit_command(layer, 'Hitung luas'):
            for i, feature in enumerate(features):
                if i % 50 == 0 and not progress.step(i):
                    break
                if not feature.hasGeometry():
                    continue
                area = measure_area(da, feature.geometry(), unit)
                total_area += area
                value = int(round(area)) if as_int else round(area, decimals)
                layer.changeAttributeValue(feature.id(), idx, value)
                count += 1
        progress.close()

        unit_label = 'ha' if unit == AREA_HA else 'm²'
        push(self.iface, 'Luas {} bidang diperbarui di kolom "{}". Total: '
                         '{:,.{}f} {}.'.format(count,
                                               layer.fields().at(idx).name(),
                                               total_area, decimals,
                                               unit_label), MSG_SUCCESS, 10)
        if as_int and decimals > 0:
            push(self.iface, 'Kolom target bertipe bilangan bulat, nilai '
                             'dibulatkan tanpa desimal.', MSG_WARNING)
