# -*- coding: utf-8 -*-
"""Widget daftar kolom bercentang yang dipakai beberapa alat."""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
    QWidget,
)


class FieldChecklist(QWidget):
    def __init__(self, layer, indexes, checked=True, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        fields = layer.fields()
        for i in indexes:
            item = QListWidgetItem(fields.at(i).name())
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if checked
                               else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list)
        row = QHBoxLayout()
        btn_all = QPushButton('Pilih semua')
        btn_none = QPushButton('Kosongkan')
        btn_all.clicked.connect(lambda: self.set_all(True))
        btn_none.clicked.connect(lambda: self.set_all(False))
        row.addWidget(btn_all)
        row.addWidget(btn_none)
        row.addStretch(1)
        layout.addLayout(row)

    def set_all(self, state):
        for r in range(self.list.count()):
            self.list.item(r).setCheckState(
                Qt.CheckState.Checked if state else Qt.CheckState.Unchecked)

    def checked_indexes(self):
        result = []
        for r in range(self.list.count()):
            item = self.list.item(r)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result
