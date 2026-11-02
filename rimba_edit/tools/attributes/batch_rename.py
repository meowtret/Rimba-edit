# -*- coding: utf-8 -*-
"""Cari & ganti teks pada sebuah kolom teks."""
import re

from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QVBoxLayout,
)

from ...core.utils import (
    ACCEPTED, MSG_INFO, MSG_SUCCESS, edit_command, ensure_editable,
    exec_dialog, get_vector_layer, is_null, is_text_field, push, warn,
    writable_field_indexes,
)

TITLE = 'Cari & Ganti Nilai'


def replace_value(text, find, repl, case_sensitive, whole):
    """Kembalikan teks baru, atau None bila tidak ada yang cocok."""
    if whole:
        same = text == find if case_sensitive else \
            text.lower() == find.lower()
        return repl if same else None
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(find), flags)
    if not pattern.search(text):
        return None
    return pattern.sub(lambda m: repl, text)


class BatchRenameDialog(QDialog):
    def __init__(self, layer, indexes, has_selection, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.field = QComboBox()
        for i in indexes:
            self.field.addItem(layer.fields().at(i).name(), i)
        self.find = QLineEdit()
        self.repl = QLineEdit()
        form.addRow('Kolom:', self.field)
        form.addRow('Cari:', self.find)
        form.addRow('Ganti dengan:', self.repl)
        layout.addLayout(form)
        self.case = QCheckBox('Bedakan huruf besar/kecil')
        self.case.setChecked(True)
        self.whole = QCheckBox('Hanya bila seluruh isi kolom sama persis')
        self.selected_only = QCheckBox('Hanya pada bidang terpilih')
        self.selected_only.setChecked(has_selection)
        self.selected_only.setEnabled(has_selection)
        for w in (self.case, self.whole, self.selected_only):
            layout.addWidget(w)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class BatchRename:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        layer = get_vector_layer(self.iface, TITLE)
        if not layer:
            return
        fields = layer.fields()
        indexes = [i for i in writable_field_indexes(layer)
                   if is_text_field(fields.at(i))]
        if not indexes:
            warn(TITLE, 'Layer tidak memiliki kolom teks yang dapat diubah.')
            return

        has_sel = layer.selectedFeatureCount() > 0
        dialog = BatchRenameDialog(layer, indexes, has_sel,
                                   self.iface.mainWindow())
        if exec_dialog(dialog) != ACCEPTED:
            return
        find = dialog.find.text()
        if not find:
            warn(TITLE, 'Teks yang dicari tidak boleh kosong.')
            return
        idx = dialog.field.currentData()
        repl = dialog.repl.text()
        case = dialog.case.isChecked()
        whole = dialog.whole.isChecked()

        features = layer.selectedFeatures() if dialog.selected_only.isChecked() \
            else layer.getFeatures()
        changes = []
        for feature in features:
            value = feature.attribute(idx)
            if is_null(value):
                continue
            new_value = replace_value(str(value), find, repl, case, whole)
            if new_value is not None and new_value != value:
                changes.append((feature.id(), new_value, value))

        if not changes:
            push(self.iface, 'Tidak ditemukan "{}" pada kolom {}.'.format(
                find, fields.at(idx).name()), MSG_INFO)
            return
        if not ensure_editable(layer, TITLE):
            return
        with edit_command(layer, 'Cari & ganti nilai'):
            for fid, new_value, old_value in changes:
                layer.changeAttributeValue(fid, idx, new_value, old_value)
        push(self.iface, '"{}" -> "{}" diganti pada {} bidang.'.format(
            find, repl, len(changes)), MSG_SUCCESS)
