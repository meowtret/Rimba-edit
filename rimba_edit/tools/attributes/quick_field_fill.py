# -*- coding: utf-8 -*-
"""Isi beberapa kolom sekaligus untuk bidang terpilih.

Nilai dikonversi sesuai tipe kolom sebelum ditulis; ketik NULL untuk
mengosongkan kolom.
"""
from qgis.PyQt.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QScrollArea,
    QVBoxLayout, QWidget,
)

from ...core.utils import (
    ACCEPTED, MSG_SUCCESS, edit_command, ensure_editable, exec_dialog,
    get_vector_layer, push, warn, writable_field_indexes,
)

TITLE = 'Isi Kolom Cepat'


def convert_value(field, text):
    """Kembalikan (ok, nilai, pesan)."""
    if text.strip().upper() == 'NULL':
        return True, None, ''
    try:
        result = field.convertCompatible(text)
    except ValueError as exc:
        return False, None, str(exc)
    except Exception as exc:  # pragma: no cover
        return False, None, str(exc)
    # Beberapa versi mengembalikan (bool, nilai)
    if isinstance(result, tuple):
        ok = bool(result[0])
        return ok, result[1] if len(result) > 1 else text, ''
    return True, result, ''


class QuickFillDialog(QDialog):
    def __init__(self, layer, indexes, count, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumWidth(440)
        self.setMinimumHeight(420)
        self.inputs = {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            'Isi kolom yang ingin diperbarui untuk {} bidang terpilih.\n'
            'Biarkan kosong untuk melewati kolom. Ketik NULL untuk '
            'mengosongkan.'.format(count)))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        form = QFormLayout(container)
        fields = layer.fields()
        for i in indexes:
            fld = fields.at(i)
            edit = QLineEdit()
            edit.setPlaceholderText(fld.typeName() or '')
            self.inputs[i] = edit
            form.addRow(fld.name(), edit)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {i: w.text() for i, w in self.inputs.items()
                if w.text().strip() != ''}


class QuickFieldFill:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        layer = get_vector_layer(self.iface, TITLE)
        if not layer:
            return
        selected = layer.selectedFeatures()
        if not selected:
            warn(TITLE, 'Pilih bidang yang ingin diperbarui.')
            return
        indexes = writable_field_indexes(layer)
        if not indexes:
            warn(TITLE, 'Layer tidak memiliki kolom yang dapat diisi.')
            return

        dialog = QuickFillDialog(layer, indexes, len(selected),
                                 self.iface.mainWindow())
        if exec_dialog(dialog) != ACCEPTED:
            return
        raw = dialog.values()
        if not raw:
            return

        fields = layer.fields()
        converted = {}
        errors = []
        for idx, text in raw.items():
            ok, value, msg = convert_value(fields.at(idx), text)
            if not ok:
                errors.append('- {}: "{}" tidak cocok dengan tipe {} {}'.format(
                    fields.at(idx).name(), text, fields.at(idx).typeName(),
                    msg).strip())
            converted[idx] = value
        if errors:
            warn(TITLE, 'Nilai berikut tidak dapat dipakai:\n' +
                 '\n'.join(errors))
            return

        if not ensure_editable(layer, TITLE):
            return
        with edit_command(layer, 'Isi kolom cepat'):
            for feature in selected:
                for idx, value in converted.items():
                    layer.changeAttributeValue(feature.id(), idx, value,
                                               feature.attribute(idx))

        push(self.iface, '{} kolom diperbarui pada {} bidang.'.format(
            len(converted), len(selected)), MSG_SUCCESS)
