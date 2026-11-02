# -*- coding: utf-8 -*-
"""Perbaiki geometri tidak valid (pengganti "Tutup Poligon Otomatis").

Hanya fitur yang benar-benar tidak valid (menurut GEOS) yang diubah.
Hasil perbaikan disesuaikan kembali dengan tipe geometri layer. Fitur yang
tidak dapat diperbaiki tanpa mengubah tipe (mis. pecah menjadi 2 bagian di
layer singlepart) tidak diubah, melainkan dipilih untuk ditinjau manual.
"""
from ...core.utils import (
    GEOM_LINE, GEOM_POLYGON, MSG_INFO, MSG_SUCCESS, MSG_WARNING, Progress,
    ask, edit_command, ensure_editable, get_vector_layer, push,
    repair_geometry,
)

TITLE = 'Perbaiki Geometri'


class RepairGeometry:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        layer = get_vector_layer(self.iface, TITLE, (GEOM_POLYGON, GEOM_LINE))
        if not layer:
            return

        selected = layer.selectedFeatures()
        if selected:
            features = selected
            scope = '{} bidang terpilih'.format(len(selected))
        else:
            if not ask(TITLE, 'Tidak ada bidang terpilih.\nPeriksa SEMUA {} '
                       'fitur di layer "{}"?'.format(layer.featureCount(),
                                                     layer.name())):
                return
            features = list(layer.getFeatures())
            scope = 'semua fitur'

        invalid = [f for f in features
                   if f.hasGeometry() and not f.geometry().isGeosValid()]
        if not invalid:
            push(self.iface, 'Semua geometri pada {} sudah valid.'.format(
                scope), MSG_INFO)
            return

        if not ensure_editable(layer, TITLE):
            return

        fixed = 0
        failed = []
        progress = Progress(TITLE, 'Memperbaiki geometri...', len(invalid))
        with edit_command(layer, 'Perbaiki geometri tidak valid'):
            for i, feature in enumerate(invalid):
                if not progress.step(i):
                    break
                new_geom = repair_geometry(feature.geometry(), layer)
                if new_geom is None or not new_geom.isGeosValid():
                    failed.append(feature.id())
                    continue
                if layer.changeGeometry(feature.id(), new_geom):
                    fixed += 1
                else:
                    failed.append(feature.id())
        progress.close()

        if failed:
            layer.selectByIds(failed)
            push(self.iface,
                 '{} geometri diperbaiki. {} tidak dapat diperbaiki otomatis '
                 '(kemungkinan hasilnya menjadi multipart di layer '
                 'singlepart) dan sekarang TERPILIH untuk ditinjau.'.format(
                     fixed, len(failed)), MSG_WARNING, 10)
        else:
            push(self.iface, '{} dari {} geometri tidak valid berhasil '
                             'diperbaiki ({}).'.format(fixed, len(invalid),
                                                       scope), MSG_SUCCESS)
