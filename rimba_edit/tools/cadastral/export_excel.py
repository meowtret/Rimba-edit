# -*- coding: utf-8 -*-
"""Ekspor atribut bidang ke Excel (.xlsx).

Memakai openpyxl bila tersedia (header berwarna, huruf Arial, baris judul
dibekukan). Bila openpyxl tidak ada, memakai penulis XLSX bawaan QGIS/GDAL.
"""
import os

from qgis.core import QgsProject, QgsVectorFileWriter
from qgis.PyQt.QtCore import QDateTime
from qgis.PyQt.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QLabel, QVBoxLayout,
)

from ...core.utils import (
    ACCEPTED, AREA_HA, GEOM_POLYGON, MSG_SUCCESS, area_calculator,
    exec_dialog, get_vector_layer, measure_area, push, safe_sheet_name,
    to_python, warn,
)
from ..attributes.field_picker import FieldChecklist

TITLE = 'Ekspor ke Excel'


class ExportDialog(QDialog):
    def __init__(self, layer, has_selection, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumWidth(400)
        self.setMinimumHeight(420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Kolom yang diekspor:'))
        self.fields = FieldChecklist(layer, range(layer.fields().count()))
        layout.addWidget(self.fields)
        self.selected_only = QCheckBox('Hanya bidang terpilih ({})'.format(
            layer.selectedFeatureCount()))
        self.selected_only.setChecked(has_selection)
        self.selected_only.setEnabled(has_selection)
        layout.addWidget(self.selected_only)
        self.add_area = QCheckBox('Tambahkan kolom luas hitungan (ha)')
        self.add_area.setVisible(layer.geometryType() == GEOM_POLYGON)
        layout.addWidget(self.add_area)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def write_openpyxl(path, sheet_name, headers, rows):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = safe_sheet_name(sheet_name)
    header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79',
                              fill_type='solid')
    header_font = Font(name='Arial', color='FFFFFF', bold=True)
    body_font = Font(name='Arial')
    for col, name in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    widths = [len(str(h)) for h in headers]
    for r, row in enumerate(rows, start=2):
        for c, value in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.font = body_font
            if value is not None:
                widths[c - 1] = max(widths[c - 1], len(str(value)))
    for c, width in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=c).column_letter].width = \
            min(width + 3, 50)
    ws.freeze_panes = 'A2'
    wb.save(path)


def write_gdal(layer, path, indexes, selected_only):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'XLSX'
    options.fileEncoding = 'UTF-8'
    options.onlySelectedFeatures = selected_only
    options.attributes = list(indexes)
    options.layerName = safe_sheet_name(layer.name())
    context = QgsProject.instance().transformContext()
    if hasattr(QgsVectorFileWriter, 'writeAsVectorFormatV3'):
        result = QgsVectorFileWriter.writeAsVectorFormatV3(layer, path,
                                                           context, options)
    else:  # pragma: no cover
        result = QgsVectorFileWriter.writeAsVectorFormatV2(layer, path,
                                                           context, options)
    error, message = result[0], result[1]
    try:
        ok = int(error) == 0
    except Exception:
        ok = getattr(error, 'name', '') == 'NoError'
    if not ok:
        raise RuntimeError(message or 'Gagal menulis file XLSX')


class ExportExcel:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        layer = get_vector_layer(self.iface, TITLE)
        if not layer:
            return
        has_sel = layer.selectedFeatureCount() > 0
        dialog = ExportDialog(layer, has_sel, self.iface.mainWindow())
        if exec_dialog(dialog) != ACCEPTED:
            return
        indexes = dialog.fields.checked_indexes()
        if not indexes:
            warn(TITLE, 'Pilih minimal satu kolom.')
            return
        selected_only = dialog.selected_only.isChecked()
        add_area = layer.geometryType() == GEOM_POLYGON and \
            dialog.add_area.isChecked()

        default = '{}_{}.xlsx'.format(
            layer.name(), QDateTime.currentDateTime().toString('yyyyMMdd_HHmm'))
        path, _ = QFileDialog.getSaveFileName(
            self.iface.mainWindow(), 'Simpan File Excel', default,
            'Excel (*.xlsx)')
        if not path:
            return
        if not path.lower().endswith('.xlsx'):
            path += '.xlsx'

        features = layer.selectedFeatures() if selected_only \
            else list(layer.getFeatures())
        fields = layer.fields()

        try:
            import openpyxl  # noqa: F401
            has_openpyxl = True
        except ImportError:
            has_openpyxl = False

        try:
            if has_openpyxl:
                headers = [fields.at(i).name() for i in indexes]
                da = None
                if add_area:
                    headers.append('LUAS_HITUNG_HA')
                    da, _ = area_calculator(layer)
                rows = []
                for f in features:
                    row = [to_python(f.attribute(i)) for i in indexes]
                    if da is not None:
                        row.append(round(measure_area(da, f.geometry(),
                                                      AREA_HA), 4)
                                   if f.hasGeometry() else None)
                    rows.append(row)
                write_openpyxl(path, layer.name(), headers, rows)
            else:
                if os.path.exists(path):
                    os.remove(path)
                write_gdal(layer, path, indexes, selected_only)
        except PermissionError:
            warn(TITLE, 'File tidak dapat ditulis. Pastikan file tidak '
                        'sedang dibuka di Excel.\n{}'.format(path))
            return
        except Exception as exc:
            warn(TITLE, 'Gagal mengekspor:\n{}'.format(exc))
            return

        note = '' if has_openpyxl else ' (tanpa format, openpyxl tidak ' \
                                       'terpasang)'
        push(self.iface, '{} bidang diekspor ke {}{}'.format(
            len(features), path, note), MSG_SUCCESS, 10)
