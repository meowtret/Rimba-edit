# -*- coding: utf-8 -*-
"""Salin atribut dari 1 bidang sumber ke bidang terpilih lainnya."""
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
)

from ...core.utils import (
    ACCEPTED, MSG_SUCCESS, edit_command, ensure_editable, exec_dialog,
    feature_label, get_vector_layer, push, warn, writable_field_indexes,
)
from .field_picker import FieldChecklist

TITLE = 'Salin Atribut'


class CopyDialog(QDialog):
    def __init__(self, layer, features, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Bidang SUMBER (atribut disalin dari sini):'))
        self.source = QComboBox()
        for f in features:
            self.source.addItem(feature_label(layer, f), f.id())
        layout.addWidget(self.source)
        layout.addWidget(QLabel('Kolom yang disalin ke {} bidang lain:'.format(
            len(features) - 1)))
        self.fields = FieldChecklist(layer, writable_field_indexes(layer))
        layout.addWidget(self.fields)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class CopyAttributes:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        layer = get_vector_layer(self.iface, TITLE)
        if not layer:
            return
        selected = layer.selectedFeatures()
        if len(selected) < 2:
            warn(TITLE, 'Pilih minimal 2 bidang (1 sumber + 1 atau lebih '
                        'target).')
            return

        dialog = CopyDialog(layer, selected, self.iface.mainWindow())
        if exec_dialog(dialog) != ACCEPTED:
            return
        indexes = dialog.fields.checked_indexes()
        if not indexes:
            warn(TITLE, 'Tidak ada kolom yang dipilih.')
            return
        if not ensure_editable(layer, TITLE):
            return

        source_id = dialog.source.currentData()
        source = next(f for f in selected if f.id() == source_id)
        targets = [f for f in selected if f.id() != source_id]

        with edit_command(layer, 'Salin atribut'):
            for target in targets:
                for idx in indexes:
                    layer.changeAttributeValue(target.id(), idx,
                                               source.attribute(idx),
                                               target.attribute(idx))

        push(self.iface, '{} kolom disalin ke {} bidang.'.format(
            len(indexes), len(targets)), MSG_SUCCESS)
