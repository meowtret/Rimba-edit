# -*- coding: utf-8 -*-
"""Validasi kolom wajib: sorot merah bidang yang kolom wajibnya kosong.

Gaya asli layer TIDAK hilang: alat ini membuat gaya baru bernama
"Validasi Rimba Edit" di Style Manager layer, sehingga gaya semula bisa
dikembalikan lewat tombol di dialog atau klik kanan layer > Styles.
"""
from qgis.core import (
    QgsExpression, QgsFeatureRequest, QgsRuleBasedRenderer, QgsSymbol,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QLabel, QPushButton, QVBoxLayout,
)

from ...core.utils import (
    ACCEPTED, MSG_INFO, MSG_SUCCESS, MSG_WARNING, REQUEST_NO_GEOMETRY,
    exec_dialog,
    get_vector_layer, is_text_field, push, warn,
)
from ..attributes.field_picker import FieldChecklist

TITLE = 'Validasi Kolom Wajib'
STYLE_NAME = 'Validasi Rimba Edit'
PREV_STYLE_KEY = 'rimba_edit/prev_style'
FIELDS_KEY = 'rimba_edit/mandatory_fields'


def build_null_expression(layer, names):
    parts = []
    fields = layer.fields()
    for name in names:
        ref = QgsExpression.quotedColumnRef(name)
        fld = fields.at(fields.indexOf(name))
        if is_text_field(fld):
            parts.append("({0} IS NULL OR trim({0}) = '')".format(ref))
        else:
            parts.append('({} IS NULL)'.format(ref))
    return ' OR '.join(parts)


def restore_style(layer):
    manager = layer.styleManager()
    prev = layer.customProperty(PREV_STYLE_KEY)
    if prev and prev in manager.styles():
        manager.setCurrentStyle(prev)
    if STYLE_NAME in manager.styles() and \
            manager.currentStyle() != STYLE_NAME:
        manager.removeStyle(STYLE_NAME)
    layer.removeCustomProperty(PREV_STYLE_KEY)
    layer.triggerRepaint()


class ValidasiDialog(QDialog):
    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumWidth(400)
        self.setMinimumHeight(440)
        self.restore_requested = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Centang kolom wajib. Bidang dengan kolom wajib '
                                'kosong disorot MERAH, yang lengkap HIJAU.'))
        fields = layer.fields()
        self.fields = FieldChecklist(layer, range(fields.count()), False)
        remembered = layer.customProperty(FIELDS_KEY) or []
        if isinstance(remembered, str):
            remembered = [remembered]
        self._apply_remembered(remembered)
        layout.addWidget(self.fields)

        self.select_bad = QCheckBox('Pilih (select) bidang yang belum lengkap')
        self.select_bad.setChecked(True)
        layout.addWidget(self.select_bad)

        if layer.styleManager().currentStyle() == STYLE_NAME:
            btn_restore = QPushButton('Kembalikan gaya semula')
            btn_restore.clicked.connect(self._restore)
            layout.addWidget(btn_restore)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_remembered(self, names):
        for r in range(self.fields.list.count()):
            item = self.fields.list.item(r)
            if item.text() in names:
                item.setCheckState(Qt.CheckState.Checked)

    def _restore(self):
        self.restore_requested = True
        self.reject()


class ValidasiHighlight:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        layer = get_vector_layer(self.iface, TITLE)
        if not layer:
            return
        dialog = ValidasiDialog(layer, self.iface.mainWindow())
        result = exec_dialog(dialog)
        if dialog.restore_requested:
            restore_style(layer)
            push(self.iface, 'Gaya semula layer dikembalikan.', MSG_INFO)
            return
        if result != ACCEPTED:
            return

        fields = layer.fields()
        names = [fields.at(i).name() for i in dialog.fields.checked_indexes()]
        if not names:
            warn(TITLE, 'Centang minimal satu kolom wajib.')
            return
        layer.setCustomProperty(FIELDS_KEY, names)

        null_expr = build_null_expression(layer, names)
        expression = QgsExpression(null_expr)
        if expression.hasParserError():
            warn(TITLE, 'Ekspresi tidak valid: {}'.format(
                expression.parserErrorString()))
            return

        # Hitung dengan ekspresi yang SAMA dengan simbologi -> angka konsisten
        request = QgsFeatureRequest().setFilterExpression(null_expr)
        request.setFlags(REQUEST_NO_GEOMETRY)
        request.setNoAttributes()
        bad_ids = [f.id() for f in layer.getFeatures(request)]
        total = layer.featureCount()

        # Simpan gaya asli lalu pindah ke gaya validasi
        manager = layer.styleManager()
        if manager.currentStyle() != STYLE_NAME:
            layer.setCustomProperty(PREV_STYLE_KEY, manager.currentStyle())
            if STYLE_NAME in manager.styles():
                manager.removeStyle(STYLE_NAME)
            manager.addStyleFromLayer(STYLE_NAME)
            manager.setCurrentStyle(STYLE_NAME)

        root = QgsRuleBasedRenderer.Rule(None)
        for label, expr, fill, line in (
                ('Kolom wajib kosong', null_expr, '#dc3232', '#b40000'),
                ('Lengkap', 'NOT ({})'.format(null_expr), '#32b432',
                 '#007800')):
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(QColor(fill))
            try:
                symbol.symbolLayer(0).setStrokeColor(QColor(line))
            except Exception:
                pass
            symbol.setOpacity(0.8)
            rule = QgsRuleBasedRenderer.Rule(symbol, 0, 0, expr, label)
            root.appendChild(rule)
        layer.setRenderer(QgsRuleBasedRenderer(root))
        layer.triggerRepaint()
        self.iface.layerTreeView().refreshLayerSymbology(layer.id())

        if dialog.select_bad.isChecked():
            layer.selectByIds(bad_ids)

        level = MSG_WARNING if bad_ids else MSG_SUCCESS
        push(self.iface,
             'Total {} bidang: {} lengkap, {} belum lengkap (kolom: {}). '
             'Jalankan lagi alat ini untuk mengembalikan gaya semula.'.format(
                 total, total - len(bad_ids), len(bad_ids), ', '.join(names)),
             level, 12)
